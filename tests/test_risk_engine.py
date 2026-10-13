"""Risk scores stay in range and do not treat a stockout as low demand."""

import math

from src.risk_engine import BASELINE_COVER_DAYS, WEIGHTS, assess, baseline_alert


def test_weights_sum_to_one():
    assert math.isclose(sum(WEIGHTS.values()), 1.0)


def test_score_is_stable_and_bounded():
    kwargs = dict(
        on_hand=40,
        pipeline_before_arrival=10,
        expected_daily_demand=30,
        baseline_daily_demand=28,
        replenishment_days=2,
        extra_delay_days=4,
        upstream_capacity_ratio=0.2,
    )
    first = assess(**kwargs)
    second = assess(**kwargs)
    assert first == second
    assert 0.0 <= first["risk_score"] <= 1.0
    assert first["alert"] is True
    assert first["dominant_feature"] in WEIGHTS


def test_zero_demand_does_not_divide_or_alert():
    result = assess(
        on_hand=0,
        pipeline_before_arrival=0,
        expected_daily_demand=0,
        baseline_daily_demand=0,
        replenishment_days=1,
        extra_delay_days=0,
        upstream_capacity_ratio=0,
    )
    assert result["alert"] is False
    assert result["cover_days"] is None
    assert result["risk_score"] == 0.0
    assert baseline_alert(on_hand=0, expected_daily_demand=0) is False


def test_low_requested_demand_does_not_reduce_score_below_cover_risk():
    tight = assess(
        on_hand=5,
        pipeline_before_arrival=0,
        expected_daily_demand=10,
        baseline_daily_demand=20,
        replenishment_days=2,
        extra_delay_days=0,
        upstream_capacity_ratio=1,
    )
    normal = assess(
        on_hand=5,
        pipeline_before_arrival=0,
        expected_daily_demand=10,
        baseline_daily_demand=10,
        replenishment_days=2,
        extra_delay_days=0,
        upstream_capacity_ratio=1,
    )
    assert tight["features"]["demand_pressure"] == 0.0
    assert tight["risk_score"] == normal["risk_score"]
    assert "requested demand" in tight["explanation"]


def test_hard_shortfall_uses_pipeline_and_lead_time():
    covered = assess(
        on_hand=10,
        pipeline_before_arrival=10,
        expected_daily_demand=10,
        baseline_daily_demand=10,
        replenishment_days=2,
        extra_delay_days=0,
        upstream_capacity_ratio=1,
    )
    short = assess(
        on_hand=10,
        pipeline_before_arrival=0,
        expected_daily_demand=10,
        baseline_daily_demand=10,
        replenishment_days=2,
        extra_delay_days=0,
        upstream_capacity_ratio=1,
    )
    assert covered["hard_shortfall"] is False
    assert short["hard_shortfall"] is True


def test_baseline_threshold_ignores_pipeline():
    assert baseline_alert(on_hand=10, expected_daily_demand=10) is True
    assert BASELINE_COVER_DAYS == 2.0
    assert baseline_alert(on_hand=20, expected_daily_demand=10) is False
