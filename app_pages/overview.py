import pandas as pd
import streamlit as st

from src.figures import service_timeline
from src.ui import as_of_day, fmt_num, fmt_pct, require_bundle, scenario_line, versus_baseline

bundle = require_bundle()
scenario = bundle["scenario"]
compared = versus_baseline(pd.DataFrame(bundle["summaries"]))
base = compared.loc[compared["policy"] == "do_nothing"].iloc[0]
ranked = compared.sort_values(["unmet_demand_crates", "stockout_events", "transport_cost_units"]).iloc[0]
do_nothing = bundle["results"]["do_nothing"]
day = as_of_day(scenario.horizon)
risk = do_nothing.forward(do_nothing.risk)
morning = risk.loc[risk["day"] == day]
flagged = morning.loc[morning["echo_alert"] & morning["type"].isin(["hub", "retailer"])]

st.title("Executive overview")
st.caption(scenario_line(scenario))
st.caption("Do nothing is the top row. The second row is the same shock under the other two policies. Turn on Play mornings in the sidebar to walk the dotted line through the days.")

gap = round(float(ranked["unmet_demand_crates"] - base["unmet_demand_crates"]), 1)
with st.container(horizontal=True):
    st.metric(
        "Service level",
        fmt_pct(base["service_level"]),
        border=True,
        help="Served crates divided by requested demand, do nothing.",
    )
    if ranked["policy"] == "do_nothing" or abs(gap) < 0.05:
        st.metric(
            "Unmet demand",
            f"{fmt_num(base['unmet_demand_crates'])} crates",
            border=True,
            help="Simulated lost sales. No other policy reduced this total.",
        )
    else:
        st.metric(
            "Unmet demand",
            f"{fmt_num(base['unmet_demand_crates'])} crates",
            delta=gap,
            delta_color="inverse",
            border=True,
            help=f"Crates of unmet demand under {ranked['policy_label']} minus do nothing. Negative means fewer lost crates.",
        )
    st.metric("Stockout events", int(base["stockout_events"]), border=True, help="Separate spells of unmet demand above 0.5 crates.")
    st.metric("Alerts this morning", int(len(flagged)), border=True, help=f"Hub and retailer alerts on morning {day}, before demand is served.")

today = do_nothing.daily_service.loc[do_nothing.daily_service["day"] == day]
unmet_today = float(today["unmet_demand"].iloc[0]) if not today.empty else 0.0
recovery_label = {
    "not recovered within horizon": "Still open",
    "no service break below 95%": "Held above 95%",
    "recovered": "Recovered",
    "undefined": "Undefined",
}.get(str(base["recovery_status"]), str(base["recovery_status"]))
with st.container(horizontal=True):
    st.metric(
        "Estimated spoilage",
        f"{fmt_num(base['estimated_spoilage_crates'])} crates",
        border=True,
        help="Assumed hub and retailer loss. Not weighed waste.",
    )
    st.metric(
        "Transport cost",
        fmt_num(base["transport_cost_units"], 0),
        border=True,
        help="Synthetic cost units, not rupees.",
    )
    st.metric(
        "Recovery",
        recovery_label,
        border=True,
        help=f"Computed status: {base['recovery_status']}. The clock starts only when network service falls below 95%.",
    )
    st.metric(
        f"Unmet on day {day}",
        f"{fmt_num(unmet_today)} crates",
        border=True,
        help="Lost sales on this morning under do nothing. Play mornings steps this number through the run.",
    )

st.subheader("Same shock, three policies")
with st.container(horizontal=True):
    for row in compared.itertuples(index=False):
        if row.policy == "do_nothing":
            delta = None
        else:
            delta = f"{row.unmet_vs_do_nothing:+.1f} crates"
        st.metric(
            row.policy_label,
            f"{fmt_num(row.unmet_demand_crates, 0)} crates unmet",
            delta=delta,
            delta_color="inverse",
            border=True,
            help=f"Service {fmt_pct(row.service_level)}. Stockout events {int(row.stockout_events)}. Spoilage {fmt_num(row.estimated_spoilage_crates)} crates. Cost {fmt_num(row.transport_cost_units, 0)}.",
        )

chart, note = st.columns((1.45, 1), gap="medium")
with chart:
    st.plotly_chart(
        service_timeline(
            {policy: result.daily_service for policy, result in bundle["results"].items()},
            shock_start=scenario.start_day,
            shock_end=scenario.end_day,
            show_shock=scenario.kind != "none",
            mark_day=day,
        ),
        width="stretch",
    )
with note:
    st.subheader("What to read from this run")
    st.write(bundle["recommendation"])

st.subheader(f"Alerts on morning {day}")
if flagged.empty:
    st.caption(f"Morning {day} is quiet. No hub or retailer is flagged. Move the morning slider if you want a later day in the shock.")
else:
    view = flagged.sort_values("risk_score", ascending=False)[
        ["node_id", "name", "place_label", "type", "sku", "risk_level", "risk_score", "cover_days", "lead_time_days", "estimated_unmet_demand"]
    ].rename(
        columns={
            "node_id": "ID",
            "name": "Location",
            "place_label": "Place",
            "type": "Type",
            "sku": "Crop",
            "risk_level": "Level",
            "risk_score": "Score",
            "cover_days": "Cover (days)",
            "lead_time_days": "Lead time (days)",
            "estimated_unmet_demand": "Estimated unmet crates",
        }
    )
    st.dataframe(view, width="stretch", hide_index=True)
    st.caption("Estimated unmet crates are a projection until replenishment, not counted lost sales. The audit page keeps the full explanation.")
