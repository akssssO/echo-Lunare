import pandas as pd
import streamlit as st

from src.figures import contribution_bars
from src.risk_engine import SCORE_ALERT_THRESHOLD, WEIGHTS
from src.ui import as_of_day, fmt_num, require_bundle, scenario_line

bundle = require_bundle()
scenario = bundle["scenario"]
day = as_of_day(scenario.horizon)
risk = bundle["results"]["do_nothing"].risk
morning = risk.loc[(risk["day"] == day) & (risk["type"] == "retailer")].copy()

st.title("Early-warning engine")
st.caption(scenario_line(scenario))
st.caption(
    "Each row is one retailer and crop on the selected morning, before that day's demand is served. "
    "Recent demand is trailing requested demand, not sales. "
    f"An alert is a hard cover shortfall, or a risk score of at least {SCORE_ALERT_THRESHOLD:.2f}."
)
weights = ", ".join(f"{name.replace('_', ' ')} {value:.2f}" for name, value in WEIGHTS.items())
st.caption("Fixed weights, not fitted on the test scenarios: " + weights + ".")

if morning.empty:
    st.caption("This morning has no retailer rows to score. Press Run simulation in the sidebar.")
    st.stop()

alerts = int(morning["echo_alert"].sum())
critical = int((morning["risk_level"] == "critical").sum())
with st.container(horizontal=True):
    st.metric("Retailer rows", int(len(morning)), border=True)
    st.metric("Alerts", alerts, border=True)
    st.metric("Critical", critical, border=True)

level = st.pills(
    "Risk level",
    options=["all", "critical", "high", "moderate", "low"],
    default="all",
    selection_mode="single",
)
view = morning if level in (None, "all") else morning.loc[morning["risk_level"] == level]
if view.empty:
    st.caption(f"No retailer is {level} on morning {day}. Choose another level or another morning.")
else:
    table = view.sort_values(["echo_alert", "risk_score"], ascending=[False, False])[
        [
            "node_id",
            "name",
            "place_label",
            "sku",
            "on_hand",
            "recent_requested_demand",
            "baseline_demand",
            "upstream_capacity_ratio",
            "lead_time_days",
            "cover_days",
            "estimated_unmet_demand",
            "risk_score",
            "risk_level",
            "echo_alert",
            "dominant_feature",
        ]
    ].rename(
        columns={
            "node_id": "ID",
            "name": "Location",
            "place_label": "Place",
            "sku": "Crop",
            "on_hand": "Stock",
            "recent_requested_demand": "Recent demand",
            "baseline_demand": "Baseline demand",
            "upstream_capacity_ratio": "Supplier capacity",
            "lead_time_days": "Lead time (days)",
            "cover_days": "Cover (days)",
            "estimated_unmet_demand": "Estimated unmet",
            "risk_score": "Score",
            "risk_level": "Level",
            "echo_alert": "Alert",
            "dominant_feature": "Largest feature",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)
    st.caption("Supplier capacity is a fraction of normal production (1.00 means full). Estimated unmet demand is a projection, not observed lost sales.")

st.subheader("Why this warning")
flagged = morning.loc[morning["echo_alert"]]
if flagged.empty:
    st.caption(f"No retailer alert on morning {day}. The selector below still opens the highest score, so you can see why it stayed quiet.")
    choices = morning.sort_values("risk_score", ascending=False)
else:
    choices = flagged.sort_values("risk_score", ascending=False)
labels = [f"{row.node_id} · {row.sku} · {row.risk_level}" for row in choices.itertuples(index=False)]
picked = st.selectbox("Location and crop", options=labels)
chosen = choices.iloc[labels.index(picked)]

with st.container(border=True):
    st.markdown(f"**{chosen['name']} · {chosen['sku']} · {chosen['risk_level']}**")
    st.write(chosen["explanation"])
    with st.container(horizontal=True):
        st.metric("Stock", f"{fmt_num(chosen['on_hand'])} crates", border=True)
        st.metric("Cover", "undefined" if pd.isna(chosen["cover_days"]) else f"{fmt_num(chosen['cover_days'])} days", border=True)
        lead = chosen["lead_time_days"]
        lead_label = "No primary lane" if pd.isna(lead) else f"{int(lead)} days"
        st.metric("Lead time", lead_label, border=True)
        st.metric("Score", fmt_num(chosen["risk_score"], 2), border=True)

contrib = {
    "Cover": float(chosen["contribution_cover"]),
    "Delay": float(chosen["contribution_delay"]),
    "Demand": float(chosen["contribution_demand"]),
    "Capacity": float(chosen["contribution_capacity"]),
}
st.plotly_chart(contribution_bars(contrib), width="stretch")
st.caption(
    f"Recent requested demand {chosen['recent_requested_demand']:.1f} crates/day. "
    f"Baseline {chosen['baseline_demand']:.1f}. "
    f"Upstream capacity {chosen['upstream_capacity_ratio'] * 100:.0f}% of normal. "
    "A below-baseline week does not reduce the score."
)
