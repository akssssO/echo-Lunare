"""Deterministic synthetic observations.

This module creates demand paths and catalogue tables. It does not step
inventory; the simulation engine does that. Every series here is synthetic.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.network import SKUS, SupplyNetwork
from src.scenario import Scenario


def generate_demand_plan(net: SupplyNetwork, scenario: Scenario) -> dict[tuple[str, str, int], float]:
    """Requested daily demand for history and the forward horizon.

    Keys are (node_id, sku, day). Days in [-history_days, -1] are context.
    Days in [0, horizon) are the scenario window. The same seed and scenario
    always rebuild the same plan. Iteration order is sorted so the RNG stream
    does not depend on dict ordering.
    """
    rng = np.random.default_rng(scenario.seed)
    retailers = sorted({node_id for node_id, _sku in net.baseline_demand})
    plan: dict[tuple[str, str, int], float] = {}
    start = -scenario.history_days
    for day in range(start, scenario.horizon):
        phase = 2.0 * math.pi * ((day - start) % 7) / 7.0
        weekly = 1.0 + 0.05 * math.sin(phase)
        for node_id in retailers:
            for sku in SKUS:
                mean = net.baseline_demand.get((node_id, sku), 0.0)
                if mean <= 0:
                    continue
                noise = float(rng.normal(0.0, 0.04))
                multiplier = min(1.25, max(0.78, weekly + noise))
                if (
                    scenario.kind == "demand_surge"
                    and scenario.active(day)
                    and (scenario.demand_node_ids is None or node_id in scenario.demand_node_ids)
                ):
                    multiplier *= scenario.demand_factor
                plan[(node_id, sku, day)] = round(mean * multiplier, 4)
    return plan


def catalog_frames(net: SupplyNetwork) -> dict[str, pd.DataFrame]:
    """Readable previews of the generated network. Values are synthetic."""
    suppliers = []
    facilities = []
    for node in net.nodes.values():
        row = {
            "node_id": node.node_id,
            "name": node.name,
            "type": node.node_type,
            "place_label": node.place,
            "data_origin": "synthetic",
        }
        for sku in SKUS:
            row[f"{sku}_opening_crates"] = round(net.initial_inventory[(node.node_id, sku)], 2)
            row[f"{sku}_storage_crates"] = round(net.storage_limit[(node.node_id, sku)], 2)
            row[f"{sku}_capacity_crates_per_day"] = round(
                net.production_capacity.get((node.node_id, sku), 0.0), 2
            )
        if node.node_type == "supplier":
            suppliers.append(row)
        else:
            facilities.append(row)

    retailer_inventory = []
    demand_rows = []
    for node in net.nodes.values():
        if node.node_type != "retailer":
            continue
        for sku in SKUS:
            retailer_inventory.append(
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "place_label": node.place,
                    "sku": sku,
                    "opening_crates": round(net.initial_inventory[(node.node_id, sku)], 2),
                    "storage_crates": round(net.storage_limit[(node.node_id, sku)], 2),
                    "baseline_requested_crates_per_day": round(
                        net.baseline_demand.get((node.node_id, sku), 0.0), 2
                    ),
                    "data_origin": "synthetic",
                }
            )
            demand_rows.append(
                {
                    "node_id": node.node_id,
                    "sku": sku,
                    "baseline_requested_crates_per_day": round(
                        net.baseline_demand.get((node.node_id, sku), 0.0), 2
                    ),
                    "note": "Baseline is the mean of the synthetic demand generator, not observed sales.",
                }
            )

    routes = [
        {
            "edge_id": edge.edge_id,
            "source": edge.source,
            "target": edge.target,
            "role": edge.role,
            "lead_time_days": edge.lead_time_days,
            "capacity_crates_per_day": edge.capacity_per_day,
            "cost_units_per_crate": edge.cost_per_unit,
            "data_origin": "synthetic",
        }
        for edge in net.edges.values()
    ]
    return {
        "suppliers": pd.DataFrame(suppliers),
        "facilities": pd.DataFrame(facilities),
        "retailer_inventory": pd.DataFrame(retailer_inventory),
        "baseline_demand": pd.DataFrame(demand_rows),
        "routes": pd.DataFrame(routes),
    }


def disruption_event_frame(scenario: Scenario) -> pd.DataFrame:
    """The planned shock. This is an input, not an observed incident."""
    return pd.DataFrame(
        [
            {
                "event_id": "SCN-1",
                "name": scenario.name,
                "kind": scenario.kind,
                "start_day": scenario.start_day,
                "end_day_exclusive": scenario.end_day,
                "supplier_id": scenario.supplier_id,
                "route_id": scenario.route_id,
                "capacity_factor_remaining": scenario.capacity_factor,
                "demand_factor": scenario.demand_factor,
                "extra_lead_days": scenario.extra_lead_days,
                "demand_nodes": ""
                if scenario.demand_node_ids is None
                else ",".join(scenario.demand_node_ids),
                "seed": scenario.seed,
                "horizon_days": scenario.horizon,
                "history_days": scenario.history_days,
                "data_origin": "synthetic scenario input",
            }
        ]
    )
