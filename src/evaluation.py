"""Held-out synthetic evaluation.

Shortage label, for a retailer and SKU on morning t: 1 if simulated unmet
demand exceeds 0.5 crates on any day in [t, t + WINDOW). The label is used
only after the detector has already fired. Detectors see that morning's
stock, trailing requested demand, pipeline, lead time, and upstream capacity.

WINDOW is 3 days. A morning near the end of the horizon uses a shorter
look-ahead, cut off at the last simulated day, so an alert on a late
stockout is still scored.

ECHO alerts when projected stock cannot cover demand until primary replenishment,
or when the documented risk score reaches SCORE_ALERT_THRESHOLD.
The baseline alerts when on-hand cover is below BASELINE_COVER_DAYS.
It ignores pipeline, delay, and supplier capacity.

Precision is undefined when a detector raises no alerts. Recall is undefined
when the window contains no shortage labels. F1 is undefined unless both
precision and recall are defined. This module does not fill those cases with
favourable numbers.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from src.interventions import summarize_result
from src.network import build_network
from src.risk_engine import BASELINE_COVER_DAYS, SCORE_ALERT_THRESHOLD
from src.scenario import Scenario
from src.simulation import assert_constraints, run_policies

WINDOW = 3
STOCKOUT_CRATES = 0.5


def held_out_scenarios() -> list[Scenario]:
    """Reproducible cases. Seeds start at 1001 so they are not the demo seed."""
    common = dict(horizon=14, history_days=7, start_day=1, end_day=12)
    return [
        Scenario(name="Mild Nashik loss", kind="capacity_loss", supplier_id="SUP-NSK", capacity_factor=0.55, seed=1001, **common),
        Scenario(name="Severe Nashik loss", kind="capacity_loss", supplier_id="SUP-NSK", capacity_factor=0.15, seed=1002, **common),
        Scenario(
            name="Delhi demand surge",
            kind="demand_surge",
            demand_factor=1.8,
            demand_node_ids=("RET-DEL", "RET-NOI"),
            seed=1003,
            **common,
        ),
        Scenario(
            name="Severe Delhi demand surge",
            kind="demand_surge",
            demand_factor=2.4,
            demand_node_ids=("RET-DEL", "RET-NOI"),
            seed=1004,
            **common,
        ),
        Scenario(
            name="Nagpur–Delhi delay",
            kind="transport_delay",
            route_id="E-NGP-DEL",
            extra_lead_days=4,
            seed=1005,
            **common,
        ),
        Scenario(
            name="Long Nagpur–Delhi delay",
            kind="transport_delay",
            route_id="E-NGP-DEL",
            extra_lead_days=6,
            seed=1006,
            **common,
        ),
        Scenario(name="No disruption", kind="none", seed=1007, horizon=14, history_days=7, start_day=0, end_day=14),
        Scenario(
            name="Localised surge, aggressive sharing stress",
            kind="demand_surge",
            demand_factor=2.2,
            demand_node_ids=("RET-JAI",),
            seed=1008,
            **common,
        ),
    ]


def evaluate_suite(scenarios: list[Scenario] | None = None) -> dict[str, Any]:
    net = build_network()
    scenarios = scenarios if scenarios is not None else held_out_scenarios()
    rows: list[dict[str, Any]] = []
    detection_rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        results = run_policies(
            net,
            scenario,
            ("do_nothing", "alternate_sourcing", "redistribute", "redistribute_aggressive"),
        )
        for policy, result in results.items():
            assert_constraints(net, result)
            summary = summarize_result(result)
            summary["scenario"] = scenario.name
            summary["seed"] = scenario.seed
            summary["kind"] = scenario.kind
            rows.append(summary)
        detection = score_detector(results["do_nothing"])
        detection["scenario"] = scenario.name
        detection["seed"] = scenario.seed
        detection["kind"] = scenario.kind
        detection_rows.append(detection)
    operations = pd.DataFrame(rows)
    detection_frame = pd.DataFrame(detection_rows)
    return {
        "operations": operations,
        "detection": detection_frame,
        "detection_definition": {
            "window_days": WINDOW,
            "stockout_crates": STOCKOUT_CRATES,
            "echo_rule": (
                "Alert if on-hand plus pipeline arriving before the next primary replenishment "
                f"is below expected requested demand over that lead time, or if risk score >= {SCORE_ALERT_THRESHOLD}."
            ),
            "baseline_rule": f"Alert if on-hand / expected requested demand < {BASELINE_COVER_DAYS} days.",
            "leakage": "Labels use later unmet demand. Alert rows are computed before that day's demand is served.",
        },
        "findings": findings(operations, detection_frame),
    }


def score_detector(result) -> dict[str, Any]:
    """Day-level and event-level detection scores for one do-nothing run."""
    risk = result.forward(result.risk)
    nodes = result.forward(result.node_days)
    risk = risk.loc[risk["type"] == "retailer"].copy()
    retail = nodes.loc[nodes["type"] == "retailer"]
    horizon = int(result.scenario.horizon)
    y_true: list[int] = []
    y_echo: list[int] = []
    y_base: list[int] = []
    if risk.empty or horizon <= 0:
        empty = _prf([], [])
        return {**empty, "warning_lead_time_days": None, "lead_time_status": "undefined", "scored_days": 0,
                "false_alarms_echo": 0, "false_alarms_baseline": 0, "missed_events_echo": 0,
                "missed_events_baseline": 0, "shortage_events": 0, "detected_events_echo": 0,
                "detected_events_baseline": 0}
    unmet = {
        (row.node_id, row.sku, int(row.day)): float(row.unmet_demand)
        for row in retail.itertuples(index=False)
    }
    for row in risk.itertuples(index=False):
        day = int(row.day)
        if day < 0 or day >= horizon:
            continue
        end = min(day + WINDOW, horizon)
        shortage = any(
            unmet.get((row.node_id, row.sku, future), 0.0) > STOCKOUT_CRATES
            for future in range(day, end)
        )
        y_true.append(1 if shortage else 0)
        y_echo.append(1 if bool(row.echo_alert) else 0)
        y_base.append(1 if bool(row.baseline_alert) else 0)
    echo_scores = _prf(y_true, y_echo)
    base_scores = _prf(y_true, y_base)
    events = _event_lead_times(retail, risk)
    return {
        "scored_days": len(y_true),
        "positive_labels": int(sum(y_true)),
        "echo_precision": echo_scores["precision"],
        "echo_recall": echo_scores["recall"],
        "echo_f1": echo_scores["f1"],
        "echo_metric_note": echo_scores["note"],
        "baseline_precision": base_scores["precision"],
        "baseline_recall": base_scores["recall"],
        "baseline_f1": base_scores["f1"],
        "baseline_metric_note": base_scores["note"],
        "false_alarms_echo": int(sum(1 for truth, pred in zip(y_true, y_echo) if pred == 1 and truth == 0)),
        "false_alarms_baseline": int(sum(1 for truth, pred in zip(y_true, y_base) if pred == 1 and truth == 0)),
        "shortage_events": events["events"],
        "detected_events_echo": events["detected_echo"],
        "detected_events_baseline": events["detected_baseline"],
        "missed_events_echo": events["missed_echo"],
        "missed_events_baseline": events["missed_baseline"],
        "warning_lead_time_echo_days": events["mean_lead_echo"],
        "warning_lead_time_baseline_days": events["mean_lead_baseline"],
        "lead_time_status_echo": events["lead_status_echo"],
        "lead_time_status_baseline": events["lead_status_baseline"],
    }


def _prf(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    truth = np.asarray(y_true, dtype=int)
    pred = np.asarray(y_pred, dtype=int)
    if truth.size == 0:
        return {"precision": None, "recall": None, "f1": None, "note": "undefined: no scored days"}
    # Always call sklearn. Undefined cases are then reported as None rather than 0.
    precision, recall, f1, _support = precision_recall_fscore_support(
        truth, pred, average="binary", zero_division=0
    )
    note = "computed with sklearn.metrics.precision_recall_fscore_support on day-level labels"
    precision_out: float | None = float(precision)
    recall_out: float | None = float(recall)
    f1_out: float | None = float(f1)
    if int(truth.sum()) == 0:
        recall_out = None
        f1_out = None
        note = "recall and F1 undefined: no shortage label in the scored window"
        if int(pred.sum()) == 0:
            precision_out = None
            note = "precision, recall, and F1 undefined: no shortage labels and no alerts"
    elif int(pred.sum()) == 0:
        precision_out = None
        f1_out = None
        note = "precision and F1 undefined: the detector raised no alerts; recall is 0"
    return {"precision": precision_out, "recall": recall_out, "f1": f1_out, "note": note}


def _event_lead_times(retail: pd.DataFrame, risk: pd.DataFrame) -> dict[str, Any]:
    echo_leads: list[int] = []
    base_leads: list[int] = []
    events = 0
    missed_echo = 0
    missed_base = 0
    alerts = {
        (row.node_id, row.sku, int(row.day)): (bool(row.echo_alert), bool(row.baseline_alert))
        for row in risk.itertuples(index=False)
    }
    for (node_id, sku), group in retail.groupby(["node_id", "sku"]):
        previous = False
        start = None
        days = list(group.sort_values("day")[["day", "unmet_demand"]].itertuples(index=False))
        for index, row in enumerate(days + [None]):
            active = False if row is None else float(row.unmet_demand) > STOCKOUT_CRATES
            if active and not previous:
                start = int(row.day)
            if previous and not active and start is not None:
                events += 1
                end_index = index - 1
                _ = end_index
                echo_hit, base_hit = _first_alert(alerts, node_id, sku, start)
                if echo_hit is None:
                    missed_echo += 1
                else:
                    echo_leads.append(start - echo_hit)
                if base_hit is None:
                    missed_base += 1
                else:
                    base_leads.append(start - base_hit)
                start = None
            previous = active
    return {
        "events": events,
        "detected_echo": events - missed_echo,
        "detected_baseline": events - missed_base,
        "missed_echo": missed_echo,
        "missed_baseline": missed_base,
        "mean_lead_echo": None if not echo_leads else float(np.mean(echo_leads)),
        "mean_lead_baseline": None if not base_leads else float(np.mean(base_leads)),
        "lead_status_echo": "mean over detected events only" if echo_leads else "undefined: no detected events",
        "lead_status_baseline": "mean over detected events only" if base_leads else "undefined: no detected events",
    }


def _first_alert(alerts: dict, node_id: str, sku: str, start: int) -> tuple[int | None, int | None]:
    echo_day = None
    base_day = None
    for day in range(max(0, start - WINDOW), start + 1):
        flags = alerts.get((node_id, sku, day))
        if not flags:
            continue
        if flags[0] and echo_day is None:
            echo_day = day
        if flags[1] and base_day is None:
            base_day = day
    return echo_day, base_day


def findings(operations: pd.DataFrame, detection: pd.DataFrame) -> list[str]:
    """Sentences that quote the tables. No claimed improvement beyond these rows."""
    notes = [
        "All figures are from the synthetic held-out scenarios in this build. They are not field results.",
    ]
    if operations.empty:
        notes.append("The operations table is empty.")
        return notes
    for scenario, group in operations.groupby("scenario"):
        base = group.loc[group["policy"] == "do_nothing"].iloc[0]
        others = group.loc[group["policy"] != "do_nothing"]
        better = others.loc[others["unmet_demand_crates"] < base["unmet_demand_crates"] - 0.5]
        worse = others.loc[others["unmet_demand_crates"] > base["unmet_demand_crates"] + 0.5]
        notes.append(
            f"{scenario}: do-nothing unmet demand is {base['unmet_demand_crates']:.1f} crates, "
            f"service level is {_fmt_pct(base['service_level'])}, "
            f"stockout events {int(base['stockout_events'])}, "
            f"estimated spoilage {base['estimated_spoilage_crates']:.1f} crates, "
            f"transport cost {base['transport_cost_units']:.1f}."
        )
        if better.empty:
            notes.append(f"{scenario}: no computed intervention reduced unmet demand versus doing nothing.")
        else:
            names = ", ".join(f"{row.policy_label} ({row.unmet_demand_crates:.1f})" for row in better.itertuples())
            notes.append(f"{scenario}: lower unmet demand than doing nothing — {names}.")
        if not worse.empty:
            names = ", ".join(f"{row.policy_label} ({row.unmet_demand_crates:.1f})" for row in worse.itertuples())
            notes.append(f"{scenario}: higher unmet demand than doing nothing — {names}.")
    comparable = detection.loc[detection["positive_labels"] > 0]
    if comparable.empty:
        notes.append("No held-out scenario produced a shortage label, so recall cannot be compared.")
    else:
        for row in comparable.itertuples(index=False):
            notes.append(
                f"{row.scenario} detection: ECHO precision {_fmt_metric(row.echo_precision)}, "
                f"recall {_fmt_metric(row.echo_recall)}, F1 {_fmt_metric(row.echo_f1)}, "
                f"false alarms {int(row.false_alarms_echo)}, missed events {int(row.missed_events_echo)}, "
                f"lead time {_fmt_metric(row.warning_lead_time_echo_days)} days. "
                f"Baseline precision {_fmt_metric(row.baseline_precision)}, "
                f"recall {_fmt_metric(row.baseline_recall)}, F1 {_fmt_metric(row.baseline_f1)}, "
                f"false alarms {int(row.false_alarms_baseline)}, missed events {int(row.missed_events_baseline)}, "
                f"lead time {_fmt_metric(row.warning_lead_time_baseline_days)} days."
            )
    return notes


def _fmt_metric(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "undefined"
    return f"{float(value):.3f}"


def _fmt_pct(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "undefined"
    return f"{float(value) * 100:.1f}%"
