"""Metric definitions, including cases that must stay undefined."""

import math

from src.evaluation import _prf, evaluate_suite, held_out_scenarios
from src.network import build_network
from src.scenario import Scenario


def test_undefined_metrics_are_not_reported_as_zero():
    both_empty = _prf([], [])
    assert both_empty["precision"] is None
    assert both_empty["f1"] is None

    no_events = _prf([0, 0, 0], [0, 0, 0])
    assert no_events["precision"] is None
    assert no_events["recall"] is None
    assert no_events["f1"] is None

    alarms_without_events = _prf([0, 0, 0], [1, 0, 0])
    assert alarms_without_events["precision"] == 0.0
    assert alarms_without_events["recall"] is None
    assert alarms_without_events["f1"] is None

    silent_detector = _prf([1, 0, 0], [0, 0, 0])
    assert silent_detector["precision"] is None
    assert silent_detector["recall"] == 0.0
    assert silent_detector["f1"] is None


def test_sklearn_scores_a_simple_confusion():
    scored = _prf([1, 1, 0, 0], [1, 0, 1, 0])
    assert scored["precision"] == 0.5
    assert scored["recall"] == 0.5
    assert math.isclose(scored["f1"], 0.5)


def test_held_out_suite_runs_and_checks_constraints():
    scenarios = [
        Scenario(
            name="Severe Nashik loss",
            kind="capacity_loss",
            supplier_id="SUP-NSK",
            capacity_factor=0.15,
            seed=1002,
            horizon=10,
            history_days=3,
            start_day=1,
            end_day=8,
        ),
        Scenario(
            name="No disruption",
            kind="none",
            seed=1007,
            horizon=8,
            history_days=3,
            start_day=0,
            end_day=8,
        ),
    ]
    build_network()
    report = evaluate_suite(scenarios)
    detection = report["detection"]
    assert set(detection["scenario"]) == {"Severe Nashik loss", "No disruption"}
    none_row = detection.loc[detection["scenario"] == "No disruption"].iloc[0]
    assert none_row["positive_labels"] == 0
    assert none_row["echo_recall"] is None or (isinstance(none_row["echo_recall"], float) and math.isnan(none_row["echo_recall"]))
    operations = report["operations"]
    assert {"unmet_demand_crates", "service_level", "estimated_spoilage_crates", "transport_cost_units"} <= set(operations.columns)
    assert any("synthetic" in note.lower() or "held-out" in note.lower() or "field" in note.lower() for note in report["findings"])


def test_full_suite_is_reproducible():
    """The submission suite is deterministic. This is the slow test."""
    first = evaluate_suite(held_out_scenarios())
    second = evaluate_suite(held_out_scenarios())
    assert first["findings"] == second["findings"]
    assert first["operations"]["unmet_demand_crates"].tolist() == second["operations"]["unmet_demand_crates"].tolist()
