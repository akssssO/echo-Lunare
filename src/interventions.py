"""Feasible heuristics for advisory interventions.

These policies are not autonomous operating instructions. Each one is a
transparent rule: alternative sourcing may use an alternate lane only when
that lane has source stock and route capacity; redistribution may move stock
only after the donor keeps a protection floor, and it deducts that stock once.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.network import SupplyNetwork, descendants
from src.scenario import Scenario
from src.simulation import POLICY_LABELS, SimResult, run_policies

COMPARE_POLICIES = ("do_nothing", "alternate_sourcing", "redistribute")


def compare(net: SupplyNetwork, scenario: Scenario) -> dict[str, SimResult]:
    return run_policies(net, scenario, COMPARE_POLICIES)


def static_feasibility(net: SupplyNetwork, policy: str) -> list[str]:
    """Structural checks. Day-of stock can still make a lane unusable."""
    notes: list[str] = []
    if policy == "do_nothing":
        primary = [edge for edge in net.edges.values() if edge.role == "primary"]
        notes.append(
            f"Feasible as a baseline: replenishment stays on {len(primary)} primary lanes and does not reroute."
        )
        return notes
    if policy == "alternate_sourcing":
        alternate = [edge for edge in net.edges.values() if edge.role == "alternate"]
        if not alternate:
            notes.append("Infeasible: the network has no alternate lanes, so this policy cannot move any extra stock.")
            return notes
        producers = sorted({edge.source for edge in alternate})
        notes.append(
            "Feasible to attempt. Alternate lanes exist from "
            + ", ".join(producers)
            + ". A lane is used only when the source still has that SKU, the route has capacity left, "
            "and the lead time is the lane's own lead time. Primary stock is drawn first."
        )
        return notes
    if policy in {"redistribute", "redistribute_aggressive"}:
        lateral = [edge for edge in net.edges.values() if edge.role == "lateral"]
        if not lateral:
            notes.append("Infeasible: there is no lateral lane, so redistribution cannot be executed.")
            return notes
        floor = "1.0" if policy == "redistribute" else "0.35"
        notes.append(
            f"Feasible to attempt on {len(lateral)} lateral lanes. A donor must keep {floor} days of "
            "expected outflow. The same crates are removed from the donor and added once to the receiver's pipeline. "
            "If nobody holds surplus, the policy selects no move."
        )
        return notes
    notes.append("Unknown policy.")
    return notes


def movement_notes(result: SimResult) -> list[str]:
    """What the heuristic actually did on this run."""
    if result.decisions.empty:
        return ["No replenishment decisions were recorded."]
    forward = result.decisions.loc[result.decisions["day"] >= 0]
    notes: list[str] = []
    for action, label in (
        ("alternate", "Alternative sourcing"),
        ("lateral", "Redistribution"),
        ("unfilled", "Unfilled orders"),
    ):
        subset = forward.loc[forward["action"] == action]
        if subset.empty:
            if action == "alternate" and result.policy == "alternate_sourcing":
                notes.append(
                    "Alternative sourcing was not selected on any day. Primary lanes covered the orders, "
                    "or alternate sources had no remaining stock or route capacity."
                )
            elif action == "lateral" and result.policy.startswith("redistribute"):
                notes.append(
                    "Redistribution was not selected. No donor held surplus above its protection floor "
                    "while a receiver was short and a lateral lane had capacity."
                )
            continue
        crates = float(subset["crates"].sum())
        notes.append(f"{label}: {len(subset)} decision(s), {crates:.1f} crates recorded.")
    if not notes:
        notes.append("Only primary-lane replenishment ran. No alternate or lateral move was required.")
    return notes


def propagation_table(net: SupplyNetwork, scenario: Scenario, baseline: SimResult) -> pd.DataFrame:
    """Separate graph exposure from simulated shortage.

    Reachable downstream nodes are exposed. They are marked as a predicted
    shortage only if the do-nothing inventory run produces unmet demand.
    """
    direct: list[str] = []
    if scenario.kind == "capacity_loss" and scenario.supplier_id in net.nodes:
        direct = [scenario.supplier_id]
    elif scenario.kind == "transport_delay" and scenario.route_id in net.edges:
        edge = net.edges[scenario.route_id]
        direct = [edge.source, edge.target]
    elif scenario.kind == "demand_surge":
        if scenario.demand_node_ids:
            direct = [node_id for node_id in scenario.demand_node_ids if node_id in net.nodes]
        else:
            direct = [node.node_id for node in net.nodes.values() if node.node_type == "retailer"]
    exposed = descendants(net, direct) if direct else set()
    shortage: set[str] = set()
    unmet_by_node: dict[str, float] = {}
    forward = baseline.forward(baseline.node_days)
    if not forward.empty:
        for node_id, qty in forward.groupby("node_id")["unmet_demand"].sum().items():
            unmet_by_node[str(node_id)] = float(qty)
            if qty > 0.5:
                shortage.add(str(node_id))
    rows = []
    for node in net.nodes.values():
        if node.node_id in direct:
            relationship = "directly affected"
        elif node.node_id in exposed:
            relationship = "downstream exposed"
        else:
            relationship = "not on this disruption's downstream path"
        rows.append(
            {
                "node_id": node.node_id,
                "name": node.name,
                "type": node.node_type,
                "place_label": node.place,
                "relationship": relationship,
                "predicted_shortage": node.node_id in shortage,
                "simulated_unmet_crates": round(unmet_by_node.get(node.node_id, 0.0), 2),
                "reading": (
                    "Predicted shortage comes from the do-nothing inventory simulation. "
                    "Downstream exposure alone is not a failure."
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_result(result: SimResult) -> dict[str, Any]:
    """Operational metrics for one policy. Unmet demand is simulated lost sales."""
    forward = result.forward(result.node_days)
    retail = forward.loc[forward["type"] == "retailer"] if not forward.empty else forward
    demand = float(retail["requested_demand"].sum()) if not retail.empty else 0.0
    served = float(retail["served"].sum()) if not retail.empty else 0.0
    unmet = float(retail["unmet_demand"].sum()) if not retail.empty else 0.0
    spoilage = float(forward["spoilage_estimated"].sum()) if not forward.empty else 0.0
    ships = result.shipments
    if ships is None or ships.empty:
        transport = 0.0
    else:
        transport = float(ships.loc[ships["day"] >= 0, "cost_units"].sum())
    events = _stockout_events(retail)
    service = (served / demand) if demand > 1e-9 else None
    recovery_days, recovery_status = _recovery(result)
    return {
        "policy": result.policy,
        "policy_label": POLICY_LABELS[result.policy],
        "requested_demand_crates": round(demand, 2),
        "served_crates": round(served, 2),
        "unmet_demand_crates": round(unmet, 2),
        "unmet_demand_meaning": "simulated lost sales, not a field measurement",
        "stockout_events": events,
        "service_level": None if service is None else round(service, 4),
        "recovery_days": recovery_days,
        "recovery_status": recovery_status,
        "estimated_spoilage_crates": round(spoilage, 2),
        "spoilage_meaning": "assumption-based estimate, not observed waste",
        "transport_cost_units": round(transport, 2),
        "cost_meaning": "synthetic cost units per crate-lane, not rupees",
    }


def recommendation(summaries: list[dict[str, Any]]) -> str:
    """Advisory text built only from the summaries just computed."""
    if not summaries:
        return "No simulation results are available yet."
    def sort_key(row: dict[str, Any]) -> tuple[float, int, float]:
        unmet = row["unmet_demand_crates"]
        events = row["stockout_events"]
        cost = row["transport_cost_units"]
        return (unmet, events, cost)

    ranked = sorted(summaries, key=sort_key)
    best = ranked[0]
    baseline = next(row for row in summaries if row["policy"] == "do_nothing")
    lines = [
        "Advisory only. This is not an instruction to move real food or freight.",
        (
            f"On this synthetic run, {best['policy_label']} ranks first on simulated unmet demand "
            f"({best['unmet_demand_crates']:.1f} crates), then stockout events ({best['stockout_events']}), "
            f"then transport cost ({best['transport_cost_units']:.1f} cost units)."
        ),
    ]
    if best["policy"] == "do_nothing":
        lines.append(
            "Neither alternative sourcing nor redistribution beat doing nothing on unmet demand "
            "for this scenario. Leaving the primary lanes in place is the better of the computed options."
        )
    else:
        delta = baseline["unmet_demand_crates"] - best["unmet_demand_crates"]
        lines.append(
            f"Relative to doing nothing, simulated unmet demand is {delta:.1f} crates lower. "
            f"Transport cost moves from {baseline['transport_cost_units']:.1f} to {best['transport_cost_units']:.1f} cost units. "
            f"Estimated spoilage moves from {baseline['estimated_spoilage_crates']:.1f} to {best['estimated_spoilage_crates']:.1f} crates."
        )
    lines.append(
        "Alternative sourcing can raise cost because reserve lanes are priced higher, and it does nothing "
        "when those sources have no stock. Redistribution cannot take a donor below its protection floor, "
        "so a network-wide shortage cannot be solved by sharing."
    )
    worse = [
        row["policy_label"]
        for row in summaries
        if row["policy"] != "do_nothing" and row["unmet_demand_crates"] > baseline["unmet_demand_crates"] + 0.5
    ]
    if worse:
        lines.append(
            "These interventions increased simulated unmet demand versus doing nothing: " + ", ".join(worse) + "."
        )
    more_events = [
        f"{row['policy_label']} ({row['stockout_events']} vs {baseline['stockout_events']})"
        for row in summaries
        if row["policy"] != "do_nothing" and row["stockout_events"] > baseline["stockout_events"]
    ]
    if more_events:
        lines.append(
            "Stockout events rose under: " + ", ".join(more_events) + ". Fewer lost crates can still come with more separate stockout spells."
        )
    return " ".join(lines)


def _stockout_events(retail: pd.DataFrame) -> int:
    if retail.empty:
        return 0
    events = 0
    for (_node, _sku), group in retail.groupby(["node_id", "sku"]):
        previous = False
        for unmet in group.sort_values("day")["unmet_demand"]:
            active = float(unmet) > 0.5
            if active and not previous:
                events += 1
            previous = active
    return events


def _recovery(result: SimResult) -> tuple[int | None, str]:
    daily = result.daily_service
    if daily.empty:
        return None, "undefined"
    daily = daily.loc[daily["day"] >= 0].sort_values("day")
    broken = daily.loc[daily["service_level"].fillna(1.0) < 0.95]
    if broken.empty:
        return None, "no service break below 95%"
    first = int(broken["day"].min())
    restored = daily.loc[(daily["day"] > first) & (daily["service_level"].fillna(0.0) >= 0.95)]
    if restored.empty:
        return None, "not recovered within horizon"
    return int(restored["day"].min() - first), "recovered"
