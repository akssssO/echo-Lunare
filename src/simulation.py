"""Daily inventory simulation.

Time step: one day. Unit: crates (illustratively 20 kg). Unmet demand is lost,
not backlogged. A shipment dispatched at the end of day t arrives at the start
of day t + lead time. Supplier, route, storage, and on-hand limits are enforced.
Inventory is never allowed to go negative.

Spoilage is an assumed fraction of on-hand stock each morning. It is an estimate
from that assumption, not an observation of food waste.

Stock identity, checked at the end of every run:

    opening + production
        = on-hand + in-transit + served + spoilage + dock rejections
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.data_generator import generate_demand_plan
from src.network import (
    AGGRESSIVE_PROTECT_DAYS,
    PROTECT_DAYS,
    SKUS,
    SPOILAGE_NODE_TYPES,
    SPOILAGE_RATE,
    TARGET_COVER_DAYS,
    SupplyNetwork,
    fastest_primary_lead,
    upstream_suppliers,
)
from src.risk_engine import assess, baseline_alert
from src.scenario import Scenario

POLICIES = (
    "do_nothing",
    "alternate_sourcing",
    "redistribute",
    "redistribute_aggressive",
)

POLICY_LABELS = {
    "do_nothing": "Do nothing",
    "alternate_sourcing": "Alternative sourcing",
    "redistribute": "Inventory redistribution",
    "redistribute_aggressive": "Aggressive redistribution (stress)",
}


@dataclass
class SimResult:
    policy: str
    scenario: Scenario
    node_days: pd.DataFrame
    shipments: pd.DataFrame
    decisions: pd.DataFrame
    risk: pd.DataFrame
    ledger: dict[str, float]
    daily_service: pd.DataFrame = field(default_factory=pd.DataFrame)
    production_log: pd.DataFrame = field(default_factory=pd.DataFrame)

    def forward(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or "day" not in frame.columns:
            return frame
        return frame.loc[frame["day"] >= 0].copy()


def simulate(
    net: SupplyNetwork,
    scenario: Scenario,
    policy: str,
    demand_plan: dict[tuple[str, str, int], float] | None = None,
) -> SimResult:
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy: {policy}")
    plan = demand_plan if demand_plan is not None else generate_demand_plan(net, scenario)
    return _Engine(net, scenario, policy, plan).run()


def run_policies(
    net: SupplyNetwork,
    scenario: Scenario,
    policies: tuple[str, ...] = ("do_nothing", "alternate_sourcing", "redistribute"),
) -> dict[str, SimResult]:
    """Run several policies on one shared demand plan and opening state."""
    plan = generate_demand_plan(net, scenario)
    return {policy: simulate(net, scenario, policy, plan) for policy in policies}


class _Engine:
    def __init__(
        self,
        net: SupplyNetwork,
        scenario: Scenario,
        policy: str,
        plan: dict[tuple[str, str, int], float],
    ) -> None:
        self.net = net
        self.scenario = scenario
        self.policy = policy
        self.plan = plan
        self.on_hand = {key: float(qty) for key, qty in net.initial_inventory.items()}
        self.pipeline: dict[tuple[str, str], list[tuple[int, float, str]]] = defaultdict(list)
        self.trailing: dict[tuple[str, str], deque[float]] = {}
        for (node_id, sku), mean in net.baseline_demand.items():
            self.trailing[(node_id, sku)] = deque([mean] * 7, maxlen=7)
        self.production_total = 0.0
        self.spoilage_total = 0.0
        self.served_total = 0.0
        self.rejected_total = 0.0
        self.node_rows: list[dict[str, Any]] = []
        self.ship_rows: list[dict[str, Any]] = []
        self.decision_rows: list[dict[str, Any]] = []
        self.risk_rows: list[dict[str, Any]] = []
        self.production_rows: list[dict[str, Any]] = []
        self.demand_by_day: dict[int, list[tuple[str, str, float]]] = defaultdict(list)
        for (node_id, sku, day), qty in plan.items():
            self.demand_by_day[day].append((node_id, sku, qty))
        self.protect_days = {
            "redistribute": PROTECT_DAYS,
            "redistribute_aggressive": AGGRESSIVE_PROTECT_DAYS,
        }.get(policy)

    def run(self) -> SimResult:
        for day in range(-self.scenario.history_days, 0):
            self._step(day)
        # The warm-up shows a demand history. The forward run restarts from the
        # documented opening snapshot so warm-up stock is not carried in twice.
        self._reset_forward_state()
        opening = sum(self.on_hand.values())
        for day in range(0, self.scenario.horizon):
            self._step(day)
        closing = sum(self.on_hand.values()) + self._in_transit()
        ledger = {
            "opening": opening,
            "production": self.production_total,
            "on_hand": sum(self.on_hand.values()),
            "in_transit": self._in_transit(),
            "served": self.served_total,
            "spoilage": self.spoilage_total,
            "dock_rejection": self.rejected_total,
        }
        ledger["imbalance"] = (ledger["opening"] + ledger["production"]) - (
            closing + ledger["served"] + ledger["spoilage"] + ledger["dock_rejection"]
        )
        node_days = pd.DataFrame(self.node_rows)
        shipments = pd.DataFrame(self.ship_rows)
        decisions = pd.DataFrame(self.decision_rows)
        risk = pd.DataFrame(self.risk_rows)
        daily = _daily_service(node_days)
        self.production_log = pd.DataFrame(self.production_rows)
        return SimResult(
            policy=self.policy,
            scenario=self.scenario,
            node_days=node_days,
            shipments=shipments,
            decisions=decisions,
            risk=risk,
            ledger=ledger,
            daily_service=daily,
            production_log=self.production_log,
        )

    def _reset_forward_state(self) -> None:
        self.on_hand = {key: float(qty) for key, qty in self.net.initial_inventory.items()}
        self.pipeline = defaultdict(list)
        self.production_total = 0.0
        self.spoilage_total = 0.0
        self.served_total = 0.0
        self.rejected_total = 0.0

    def _in_transit(self) -> float:
        return sum(qty for lots in self.pipeline.values() for _day, qty, _edge in lots)

    def _step(self, day: int) -> None:
        self._produce(day)
        received = self._receive(day)
        spoiled = self._spoil()
        self._record_risk(day)
        served, unmet, demand = self._serve(day)
        shipped = self._replenish(day)
        if self.protect_days is not None:
            self._redistribute(day)
        self._append_node_rows(day, received, spoiled, served, unmet, demand, shipped)

    def _capacity_today(self, node_id: str, sku: str, day: int) -> float:
        base = self.net.production_capacity.get((node_id, sku), 0.0)
        scenario = self.scenario
        if (
            base > 0
            and scenario.kind == "capacity_loss"
            and scenario.active(day)
            and node_id == scenario.supplier_id
        ):
            return base * scenario.capacity_factor
        return base

    def _produce(self, day: int) -> None:
        for node in self.net.nodes.values():
            if node.node_type != "supplier":
                continue
            for sku in SKUS:
                cap = self._capacity_today(node.node_id, sku, day)
                if cap <= 0:
                    continue
                key = (node.node_id, sku)
                space = max(0.0, self.net.storage_limit[key] - self.on_hand[key])
                qty = min(cap, space)
                self.on_hand[key] += qty
                self.production_total += qty
                self.production_rows.append(
                    {
                        "day": day,
                        "node_id": node.node_id,
                        "sku": sku,
                        "crates": qty,
                        "capacity_limit": cap,
                    }
                )

    def _receive(self, day: int) -> dict[tuple[str, str], float]:
        received: dict[tuple[str, str], float] = defaultdict(float)
        for key, lots in list(self.pipeline.items()):
            keep: list[tuple[int, float, str]] = []
            node_id, sku = key
            for arrival, qty, edge_id in lots:
                if arrival > day:
                    keep.append((arrival, qty, edge_id))
                    continue
                if arrival < day:
                    raise RuntimeError(f"Missed arrival on {edge_id} scheduled for day {arrival}")
                space = max(0.0, self.net.storage_limit[key] - self.on_hand[key])
                accept = min(qty, space)
                reject = qty - accept
                self.on_hand[key] += accept
                self.rejected_total += reject
                received[key] += accept
            self.pipeline[key] = keep
        return received

    def _spoil(self) -> dict[tuple[str, str], float]:
        spoiled: dict[tuple[str, str], float] = {}
        for key, qty in list(self.on_hand.items()):
            node_id, sku = key
            if self.net.node(node_id).node_type not in SPOILAGE_NODE_TYPES:
                spoiled[key] = 0.0
                continue
            loss = qty * SPOILAGE_RATE[sku]
            self.on_hand[key] = qty - loss
            self.spoilage_total += loss
            spoiled[key] = loss
        return spoiled

    def _delay_map(self, day: int) -> dict[str, int]:
        scenario = self.scenario
        if scenario.kind == "transport_delay" and scenario.active(day) and scenario.route_id:
            return {scenario.route_id: scenario.extra_lead_days}
        return {}

    def _expected_demand(self, node_id: str, sku: str) -> float:
        trail = self.trailing.get((node_id, sku))
        if not trail:
            return self.net.baseline_demand.get((node_id, sku), 0.0)
        return float(sum(trail) / len(trail))

    def _record_risk(self, day: int) -> None:
        if day < 0:
            return
        delay_map = self._delay_map(day)
        for node in self.net.nodes.values():
            if node.node_type == "supplier":
                continue
            for sku in SKUS:
                expected = self._outflow_expectation(node.node_id, sku)
                if node.node_type != "retailer" and expected <= 1e-9:
                    continue
                baseline = self.net.baseline_demand.get((node.node_id, sku), 0.0)
                if node.node_type != "retailer":
                    baseline = self.net.expected_outflow.get((node.node_id, sku), 0.0)
                lead, extra = fastest_primary_lead(self.net, node.node_id, delay_map)
                pipeline_qty = self._pipeline_before(node.node_id, sku, day, lead)
                ratio = self._upstream_ratio(node.node_id, sku, day)
                key = (node.node_id, sku)
                result = assess(
                    on_hand=self.on_hand[key],
                    pipeline_before_arrival=pipeline_qty,
                    expected_daily_demand=expected,
                    baseline_daily_demand=baseline,
                    replenishment_days=lead,
                    extra_delay_days=extra,
                    upstream_capacity_ratio=ratio,
                )
                base_flag = baseline_alert(on_hand=self.on_hand[key], expected_daily_demand=expected)
                self.risk_rows.append(
                    {
                        "day": day,
                        "node_id": node.node_id,
                        "name": node.name,
                        "place_label": node.place,
                        "type": node.node_type,
                        "sku": sku,
                        "on_hand": round(self.on_hand[key], 4),
                        "recent_requested_demand": round(expected, 4),
                        "baseline_demand": round(baseline, 4),
                        "upstream_capacity_ratio": round(ratio, 4),
                        "lead_time_days": lead,
                        "cover_days": result["cover_days"],
                        "pipeline_before_arrival": round(pipeline_qty, 4),
                        "estimated_unmet_demand": result["estimated_unmet_demand"],
                        "risk_score": result["risk_score"],
                        "risk_level": result["risk_level"],
                        "echo_alert": result["alert"],
                        "baseline_alert": base_flag,
                        "hard_shortfall": result["hard_shortfall"],
                        "dominant_feature": result["dominant_feature"],
                        "explanation": result["explanation"],
                        "contribution_cover": result["contributions"]["cover_pressure"],
                        "contribution_delay": result["contributions"]["delay_pressure"],
                        "contribution_demand": result["contributions"]["demand_pressure"],
                        "contribution_capacity": result["contributions"]["capacity_pressure"],
                        "data_origin": "simulated",
                    }
                )

    def _outflow_expectation(self, node_id: str, sku: str) -> float:
        node = self.net.node(node_id)
        if node.node_type == "retailer":
            return self._expected_demand(node_id, sku)
        return self.net.expected_outflow.get((node_id, sku), 0.0)

    def _pipeline_before(self, node_id: str, sku: str, day: int, lead: int | None) -> float:
        if lead is None:
            return 0.0
        return sum(
            qty
            for arrival, qty, _edge in self.pipeline.get((node_id, sku), [])
            if day < arrival < day + lead
        )

    def _upstream_ratio(self, node_id: str, sku: str, day: int) -> float:
        suppliers = upstream_suppliers(self.net, node_id, sku)
        if not suppliers:
            return 1.0
        ratios = []
        for supplier in suppliers:
            normal = self.net.production_capacity.get((supplier, sku), 0.0)
            if normal <= 0:
                continue
            ratios.append(self._capacity_today(supplier, sku, day) / normal)
        if not ratios:
            return 1.0
        return min(ratios)

    def _serve(
        self, day: int
    ) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float], dict[tuple[str, str], float]]:
        served: dict[tuple[str, str], float] = defaultdict(float)
        unmet: dict[tuple[str, str], float] = defaultdict(float)
        demand: dict[tuple[str, str], float] = defaultdict(float)
        for node_id, sku, qty in self.demand_by_day.get(day, []):
            key = (node_id, sku)
            demand[key] = qty
            self.trailing.setdefault(key, deque(maxlen=7)).append(qty)
            available = self.on_hand[key]
            take = min(available, qty)
            self.on_hand[key] = available - take
            served[key] = take
            unmet[key] = qty - take
            self.served_total += take
        return served, unmet, demand

    def _lead(self, edge_id: str, base_lead: int, day: int) -> int:
        extra = self._delay_map(day).get(edge_id, 0)
        return base_lead + extra

    def _ship(self, day: int, edge_id: str, sku: str, qty: float, reason: str, route_left: dict[str, float]) -> float:
        if qty <= 1e-8:
            return 0.0
        edge = self.net.edges[edge_id]
        key_src = (edge.source, sku)
        qty = min(qty, route_left[edge_id], self.on_hand[key_src])
        # Floor to 4 decimals so summed shipment logs cannot round above capacity.
        qty = int(qty * 10000) / 10000.0
        if qty <= 1e-8:
            return 0.0
        self.on_hand[key_src] -= qty
        route_left[edge_id] -= qty
        arrival = day + self._lead(edge_id, edge.lead_time_days, day)
        self.pipeline[(edge.target, sku)].append((arrival, qty, edge_id))
        self.ship_rows.append(
            {
                "day": day,
                "edge_id": edge_id,
                "source": edge.source,
                "target": edge.target,
                "sku": sku,
                "crates": round(qty, 4),
                "arrival_day": arrival,
                "lead_time_days": arrival - day,
                "cost_units": round(qty * edge.cost_per_unit, 4),
                "role": edge.role,
                "policy": self.policy,
                "reason": reason,
            }
        )
        self.decision_rows.append(
            {
                "day": day,
                "node_id": edge.target,
                "sku": sku,
                "action": edge.role,
                "edge_id": edge_id,
                "crates": round(qty, 4),
                "feasible": True,
                "reason": reason,
            }
        )
        return qty

    def _candidate_edges(self, node_id: str) -> list[Any]:
        inbound = list(self.net.inbound.get(node_id, []))
        if self.policy == "alternate_sourcing":
            pool = [edge for edge in inbound if edge.role in {"primary", "alternate"}]
            pool.sort(key=lambda edge: (0 if edge.role == "primary" else 1, edge.lead_time_days, edge.cost_per_unit))
            return pool
        return [edge for edge in inbound if edge.role == "primary"]

    def _order_target(self, node_id: str, sku: str) -> float:
        node = self.net.node(node_id)
        cover = TARGET_COVER_DAYS[node.node_type]
        if node.node_type == "retailer":
            baseline = self.net.baseline_demand.get((node_id, sku), 0.0)
            trailing = self._expected_demand(node_id, sku)
            level = max(0.8 * baseline, trailing)
        else:
            level = self.net.expected_outflow.get((node_id, sku), 0.0)
        return cover * level

    def _replenish(self, day: int) -> dict[tuple[str, str], float]:
        shipped: dict[tuple[str, str], float] = defaultdict(float)
        route_left = {edge_id: edge.capacity_per_day for edge_id, edge in self.net.edges.items()}
        groups = ("retailer", "hub", "warehouse")
        for node_type in groups:
            for node in self.net.nodes.values():
                if node.node_type != node_type:
                    continue
                for sku in SKUS:
                    self._order_one(day, node.node_id, sku, route_left, shipped)
        return shipped

    def _order_one(
        self,
        day: int,
        node_id: str,
        sku: str,
        route_left: dict[str, float],
        shipped: dict[tuple[str, str], float],
    ) -> None:
        pipeline_qty = sum(qty for _arrival, qty, _edge in self.pipeline.get((node_id, sku), []))
        need = self._order_target(node_id, sku) - self.on_hand[(node_id, sku)] - pipeline_qty
        if need <= 0.05:
            return
        filled = 0.0
        for edge in self._candidate_edges(node_id):
            if need - filled <= 0.05:
                break
            reason = (
                "Primary lanes could not fill the order. This alternate lane had source stock, "
                "remaining route capacity, and a defined lead time."
                if edge.role == "alternate"
                else "Primary-lane replenishment within source inventory and route capacity."
            )
            moved = self._ship(day, edge.edge_id, sku, need - filled, reason, route_left)
            filled += moved
            shipped[(edge.source, sku)] += moved
        leftover = need - filled
        if leftover > 0.5:
            self.decision_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "sku": sku,
                    "action": "unfilled",
                    "edge_id": "",
                    "crates": round(leftover, 4),
                    "feasible": False,
                    "reason": (
                        "Not filled. Every allowed inbound lane was short of source inventory "
                        "or remaining daily route capacity. Unmet need is not invented as a delivery."
                    ),
                }
            )

    def _redistribute(self, day: int) -> None:
        assert self.protect_days is not None
        route_left = {edge.edge_id: edge.capacity_per_day for edge in self.net.edges.values()}
        for row in self.ship_rows:
            if row["day"] == day:
                route_left[row["edge_id"]] = max(0.0, route_left[row["edge_id"]] - row["crates"])
        laterals = [edge for edge in self.net.edges.values() if edge.role == "lateral"]
        for sku in SKUS:
            needs: list[tuple[float, Any]] = []
            for edge in laterals:
                gap = self._receiver_gap(edge.target, sku, day)
                if gap > 0.5:
                    needs.append((gap, edge))
            needs.sort(key=lambda item: item[0], reverse=True)
            for _gap, edge in needs:
                surplus = self._surplus(edge.source, sku)
                gap = self._receiver_gap(edge.target, sku, day)
                qty = min(surplus, gap, route_left[edge.edge_id])
                if qty <= 0.5:
                    continue
                reason = (
                    f"Donor kept {self.protect_days:.1f} days of expected outflow, then shared surplus. "
                    "The receiver was below its order-up-to level. The lateral lane had capacity. "
                    "This stock was deducted from the donor immediately and is not counted twice."
                )
                self._ship(day, edge.edge_id, sku, qty, reason, route_left)

    def _surplus(self, node_id: str, sku: str) -> float:
        assert self.protect_days is not None
        outflow = self.net.expected_outflow.get((node_id, sku), 0.0)
        protected = self.protect_days * outflow
        return max(0.0, self.on_hand[(node_id, sku)] - protected)

    def _receiver_gap(self, node_id: str, sku: str, day: int) -> float:
        """Shortage versus one day of outflow, counting only inbound due tomorrow.

        A truck booked to arrive several days later does not close today's gap.
        """
        outflow = self.net.expected_outflow.get((node_id, sku), 0.0)
        urgent = outflow * 1.0
        imminent = sum(
            qty
            for arrival, qty, _edge in self.pipeline.get((node_id, sku), [])
            if arrival <= day + 1
        )
        return max(0.0, urgent - self.on_hand[(node_id, sku)] - imminent)

    def _append_node_rows(
        self,
        day: int,
        received: dict[tuple[str, str], float],
        spoiled: dict[tuple[str, str], float],
        served: dict[tuple[str, str], float],
        unmet: dict[tuple[str, str], float],
        demand: dict[tuple[str, str], float],
        shipped: dict[tuple[str, str], float],
    ) -> None:
        for node in self.net.nodes.values():
            for sku in SKUS:
                key = (node.node_id, sku)
                pipeline_qty = sum(qty for _arrival, qty, _edge in self.pipeline.get(key, []))
                self.node_rows.append(
                    {
                        "day": day,
                        "node_id": node.node_id,
                        "name": node.name,
                        "type": node.node_type,
                        "place_label": node.place,
                        "sku": sku,
                        "on_hand": round(self.on_hand[key], 4),
                        "received": round(received.get(key, 0.0), 4),
                        "spoilage_estimated": round(spoiled.get(key, 0.0), 4),
                        "requested_demand": round(demand.get(key, 0.0), 4),
                        "served": round(served.get(key, 0.0), 4),
                        "unmet_demand": round(unmet.get(key, 0.0), 4),
                        "shipped": round(shipped.get(key, 0.0), 4),
                        "in_transit_inbound": round(pipeline_qty, 4),
                        "data_origin": "simulated",
                    }
                )


def _daily_service(node_days: pd.DataFrame) -> pd.DataFrame:
    if node_days.empty:
        return pd.DataFrame(columns=["day", "requested_demand", "served", "unmet_demand", "service_level", "spoilage_estimated"])
    retail = node_days.loc[node_days["type"] == "retailer"]
    grouped = (
        retail.groupby("day", as_index=False)[["requested_demand", "served", "unmet_demand", "spoilage_estimated"]]
        .sum()
    )
    # Spoilage above is retailer-only. Recompute network spoilage for the cost view separately.
    grouped["service_level"] = grouped.apply(
        lambda row: (row["served"] / row["requested_demand"]) if row["requested_demand"] > 1e-9 else None,
        axis=1,
    )
    return grouped


def assert_constraints(net: SupplyNetwork, result: SimResult, tol: float = 1e-3) -> None:
    """Raise if inventory, timing, or capacity constraints were broken."""
    if abs(result.ledger["imbalance"]) > tol:
        raise AssertionError(f"Stock identity failed: imbalance={result.ledger['imbalance']}")
    forward_nodes = result.forward(result.node_days)
    if not forward_nodes.empty and (forward_nodes["on_hand"] < -tol).any():
        raise AssertionError("Negative on-hand inventory")
    if not result.shipments.empty:
        if (result.shipments["crates"] < -tol).any():
            raise AssertionError("Negative shipment")
        early = result.shipments.loc[result.shipments["arrival_day"] < result.shipments["day"] + result.shipments["lead_time_days"]]
        # arrival_day is defined as day + lead, so this catches edits that break the identity
        mismatch = result.shipments.loc[
            result.shipments["arrival_day"] != result.shipments["day"] + result.shipments["lead_time_days"]
        ]
        if not mismatch.empty or not early.empty:
            raise AssertionError("Shipment arrival does not match its lead time")
        grouped = result.shipments.groupby(["day", "edge_id"], as_index=False)["crates"].sum()
        for row in grouped.itertuples(index=False):
            cap = net.edges[row.edge_id].capacity_per_day
            if row.crates > cap + tol:
                raise AssertionError(f"Route {row.edge_id} moved {row.crates} on day {row.day} above capacity {cap}")
    if not result.production_log.empty:
        if (result.production_log["crates"] > result.production_log["capacity_limit"] + tol).any():
            raise AssertionError("Production exceeded supplier capacity")
        if (result.production_log["crates"] < -tol).any():
            raise AssertionError("Negative production")
