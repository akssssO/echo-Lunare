import streamlit as st

from src.assumptions import ASSUMPTIONS
from src.risk_engine import BASELINE_COVER_DAYS, SCORE_ALERT_THRESHOLD, WEIGHTS
from src.ui import as_of_day, require_bundle

bundle = require_bundle()
scenario = bundle["scenario"]
day = as_of_day(scenario.horizon)
risk = bundle["results"]["do_nothing"].risk
morning = risk.loc[(risk["day"] == day) & (risk["echo_alert"])].sort_values("risk_score", ascending=False)

st.title("Explainability and audit")
st.caption("Every number on this page comes from the run currently in memory. Results are simulated.")

st.subheader("Scenario parameters")
st.dataframe(bundle["events"], width="stretch", hide_index=True)

st.subheader("Evidence behind alerts")
if morning.empty:
    st.caption(f"Morning {day} has no alert under the do-nothing policy.")
else:
    evidence = morning[
        [
            "node_id",
            "name",
            "sku",
            "on_hand",
            "recent_requested_demand",
            "baseline_demand",
            "upstream_capacity_ratio",
            "lead_time_days",
            "cover_days",
            "pipeline_before_arrival",
            "estimated_unmet_demand",
            "risk_score",
            "dominant_feature",
            "hard_shortfall",
            "explanation",
        ]
    ]
    st.dataframe(evidence, width="stretch", hide_index=True)

st.subheader("Triggering conditions")
st.markdown(
    f"""
1. **Hard shortfall.** On-hand crates plus pipeline that arrives before the next primary replenishment are below expected requested demand over that lead time.
2. **Score threshold.** The weighted score reaches {SCORE_ALERT_THRESHOLD:.2f}. Weights: {", ".join(f"{key} {value:.2f}" for key, value in WEIGHTS.items())}.
3. **Baseline used only in evaluation.** On-hand cover below {BASELINE_COVER_DAYS:.0f} days, ignoring pipeline, delay, and supplier capacity.
    """
)

st.subheader("Intervention rationale")
for policy, lines in bundle["feasibility"].items():
    label = next(row["policy_label"] for row in bundle["summaries"] if row["policy"] == policy)
    st.markdown(f"**{label}**")
    for line in lines + bundle["movement"][policy]:
        st.write(line)

decisions = bundle["results"]["alternate_sourcing"].decisions
if not decisions.empty:
    sample = decisions.loc[(decisions["day"] >= 0) & (decisions["action"].isin(["alternate", "unfilled"]))]
    st.markdown("**Sample of alternative-sourcing decisions**")
    if sample.empty:
        st.caption("Alternative sourcing recorded no alternate shipment and no unfilled order in this run.")
    else:
        st.dataframe(sample.head(25), width="stretch", hide_index=True)

st.subheader("Assumptions and limitations")
for item in ASSUMPTIONS:
    st.write("• " + item)

st.caption("Opening inventory, capacities, and demand means are synthetic inputs. They are listed in the data explorer.")
