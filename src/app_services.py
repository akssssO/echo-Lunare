"""Run a scenario bundle for the app. No Streamlit imports."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.data_generator import catalog_frames, disruption_event_frame
from src.interventions import (
    compare,
    movement_notes,
    propagation_table,
    recommendation,
    static_feasibility,
    summarize_result,
)
from src.network import build_network
from src.scenario import Scenario
from src.simulation import POLICY_LABELS, assert_constraints


def execute(scenario: Scenario) -> dict[str, Any]:
    network = build_network()
    results = compare(network, scenario)
    for result in results.values():
        assert_constraints(network, result)
    summaries = [summarize_result(result) for result in results.values()]
    return {
        "scenario": scenario,
        "network": network,
        "results": results,
        "summaries": summaries,
        "recommendation": recommendation(summaries),
        "propagation": propagation_table(network, scenario, results["do_nothing"]),
        "catalog": catalog_frames(network),
        "events": disruption_event_frame(scenario),
        "feasibility": {policy: static_feasibility(network, policy) for policy in results},
        "movement": {policy: movement_notes(result) for policy, result in results.items()},
    }


def summary_frame(bundle: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(bundle["summaries"])


def forward_nodes(bundle: dict[str, Any], policy: str) -> pd.DataFrame:
    result = bundle["results"][policy]
    frame = result.forward(result.node_days)
    frame = frame.copy()
    frame.insert(0, "policy", POLICY_LABELS[policy])
    return frame


def all_forward_nodes(bundle: dict[str, Any]) -> pd.DataFrame:
    return pd.concat([forward_nodes(bundle, policy) for policy in bundle["results"]], ignore_index=True)


def history_nodes(bundle: dict[str, Any]) -> pd.DataFrame:
    result = bundle["results"]["do_nothing"]
    frame = result.node_days.loc[result.node_days["day"] < 0].copy()
    frame.insert(0, "note", "Warm-up trace. Forward inventory restarts from the opening snapshot.")
    return frame
