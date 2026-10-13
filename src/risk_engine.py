"""Transparent stockout risk scores.

The detector uses only information dated on or before the assessment morning:
on-hand stock, pipeline already dispatched, trailing requested demand,
known lead time (including a delay that has already started), and upstream
supplier capacity that is already in force. It does not read future demand,
future deliveries, or future stockouts.

Feature weights are fixed. They are not fit on the evaluation scenarios.
"""

from __future__ import annotations

from typing import Any

# Higher means more risk. Weights sum to 1.
WEIGHTS: dict[str, float] = {
    "cover_pressure": 0.50,
    "delay_pressure": 0.20,
    "demand_pressure": 0.15,
    "capacity_pressure": 0.15,
}

# Score at or above this value raises a graded warning even before the hard
# cover rule trips. The hard rule can also raise an alert on its own.
SCORE_ALERT_THRESHOLD = 0.40

# Baseline comparator: flag when on-hand cover is below this many days.
# It ignores pipeline, lead time, delays, and supplier capacity.
BASELINE_COVER_DAYS = 2.0

DELAY_NORM_DAYS = 5.0
CAPACITY_WATCH = 0.75


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def assess(
    *,
    on_hand: float,
    pipeline_before_arrival: float,
    expected_daily_demand: float,
    baseline_daily_demand: float,
    replenishment_days: int | None,
    extra_delay_days: int,
    upstream_capacity_ratio: float,
) -> dict[str, Any]:
    """Score one location and SKU.

    ``expected_daily_demand`` must be requested demand, never observed sales.
    Sales fall during a stockout even when underlying demand does not.
    ``pipeline_before_arrival`` is stock already in transit that arrives
    strictly before a new replenishment order placed this morning could arrive.
    """
    expected = max(0.0, float(expected_daily_demand))
    baseline = max(0.0, float(baseline_daily_demand))
    on_hand = max(0.0, float(on_hand))
    pipeline_before_arrival = max(0.0, float(pipeline_before_arrival))
    ratio = _clip01(float(upstream_capacity_ratio))
    extra_delay_days = max(0, int(extra_delay_days))

    if expected <= 1e-9:
        return {
            "alert": False,
            "hard_shortfall": False,
            "score_alert": False,
            "risk_score": 0.0,
            "risk_level": "low",
            "cover_days": None,
            "estimated_unmet_demand": 0.0,
            "estimated_unmet_is_estimated": True,
            "replenishment_days": replenishment_days,
            "features": {name: 0.0 for name in WEIGHTS},
            "contributions": {name: 0.0 for name in WEIGHTS},
            "dominant_feature": "cover_pressure",
            "triggers": ["no material requested demand"],
            "explanation": "No material requested demand is on file, so this SKU is not scored as a shortage risk.",
        }
    else:
        cover_days = on_hand / expected
        if replenishment_days is None:
            cover_pressure = _clip01(1.0 - cover_days / 7.0)
            hard_shortfall = on_hand + pipeline_before_arrival + 1e-6 < expected
            window_days = 7
        else:
            window = max(1, int(replenishment_days))
            cover_pressure = _clip01(1.0 - cover_days / (window + 1.0))
            available = on_hand + pipeline_before_arrival
            hard_shortfall = available + 1e-6 < expected * window
            window_days = window
        estimated_unmet = max(0.0, expected * window_days - (on_hand + pipeline_before_arrival))

    delay_pressure = _clip01(extra_delay_days / DELAY_NORM_DAYS)
    if baseline <= 1e-9:
        demand_pressure = 0.0
    else:
        # Only upward deviations add risk. A quiet week must not look like safety,
        # and this ratio is computed from requested demand, not from sales.
        demand_pressure = _clip01((expected - baseline) / baseline)
    capacity_pressure = _clip01(1.0 - ratio)

    parts = {
        "cover_pressure": cover_pressure,
        "delay_pressure": delay_pressure,
        "demand_pressure": demand_pressure,
        "capacity_pressure": capacity_pressure,
    }
    contributions = {name: WEIGHTS[name] * value for name, value in parts.items()}
    score = float(sum(contributions.values()))
    score_alert = score >= SCORE_ALERT_THRESHOLD
    alert = bool(hard_shortfall or score_alert)

    if expected <= 1e-9:
        level = "low"
        alert = False
    elif score >= 0.70 or hard_shortfall and score >= 0.55:
        level = "critical"
    elif score >= 0.50 or hard_shortfall:
        level = "high"
    elif score >= 0.25:
        level = "moderate"
    else:
        level = "low"

    triggers: list[str] = []
    if hard_shortfall and expected > 1e-9:
        triggers.append("projected stock cannot cover expected demand until replenishment")
    if score_alert:
        triggers.append(f"risk score {score:.2f} is at or above {SCORE_ALERT_THRESHOLD:.2f}")
    if not triggers:
        triggers.append("no alert condition is met")

    explanation = _explain(
        cover_days=cover_days,
        expected=expected,
        baseline=baseline,
        replenishment_days=replenishment_days,
        extra_delay_days=extra_delay_days,
        ratio=ratio,
        estimated_unmet=estimated_unmet,
        contributions=contributions,
        triggers=triggers,
        alert=alert,
    )
    return {
        "alert": alert,
        "hard_shortfall": bool(hard_shortfall) if expected > 1e-9 else False,
        "score_alert": score_alert if expected > 1e-9 else False,
        "risk_score": round(score, 4),
        "risk_level": level,
        "cover_days": None if cover_days is None else round(cover_days, 3),
        "estimated_unmet_demand": round(estimated_unmet, 3),
        "estimated_unmet_is_estimated": True,
        "replenishment_days": replenishment_days,
        "features": {name: round(value, 4) for name, value in parts.items()},
        "contributions": {name: round(value, 4) for name, value in contributions.items()},
        "dominant_feature": max(contributions, key=contributions.get),
        "triggers": triggers,
        "explanation": explanation,
    }


def baseline_alert(*, on_hand: float, expected_daily_demand: float) -> bool:
    """Threshold rule used as the evaluation comparator. No future data."""
    expected = max(0.0, float(expected_daily_demand))
    if expected <= 1e-9:
        return False
    return (max(0.0, float(on_hand)) / expected) < BASELINE_COVER_DAYS


def _explain(
    *,
    cover_days: float | None,
    expected: float,
    baseline: float,
    replenishment_days: int | None,
    extra_delay_days: int,
    ratio: float,
    estimated_unmet: float,
    contributions: dict[str, float],
    triggers: list[str],
    alert: bool,
) -> str:
    if expected <= 1e-9:
        return "No material requested demand is on file, so this SKU is not scored as a shortage risk."
    cover_txt = "undefined" if cover_days is None else f"{cover_days:.1f} days"
    lead_txt = "no inbound primary lane" if replenishment_days is None else f"{replenishment_days} days"
    ranked = sorted(contributions.items(), key=lambda item: item[1], reverse=True)
    drivers = ", ".join(f"{name.replace('_', ' ')} {value:.2f}" for name, value in ranked[:3])
    demand_txt = "in line with baseline"
    if baseline > 1e-9 and expected > baseline * 1.05:
        demand_txt = f"{(expected / baseline - 1.0) * 100:.0f}% above baseline requested demand"
    elif baseline > 1e-9 and expected < baseline * 0.95:
        demand_txt = "below baseline requested demand (this does not reduce the score)"
    status = "Alert" if alert else "No alert"
    return (
        f"{status}. Inventory cover is {cover_txt} against expected requested demand of {expected:.1f} crates/day. "
        f"Fastest primary replenishment is {lead_txt}"
        + (f", including {extra_delay_days} extra delay day(s) already in force" if extra_delay_days else "")
        + f". Upstream supplier capacity is {ratio * 100:.0f}% of normal. Recent requested demand is {demand_txt}. "
        f"Estimated unmet demand before replenishment is {estimated_unmet:.1f} crates (estimated, not observed). "
        f"Largest score contributions: {drivers}. Trigger: {triggers[0]}."
    )
