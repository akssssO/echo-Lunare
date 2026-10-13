import pandas as pd
import streamlit as st

from src.app_services import all_forward_nodes
from src.figures import metric_bars, stock_trajectories
from src.ui import csv_bytes, fmt_num, fmt_pct, require_bundle, scenario_line, versus_baseline

bundle = require_bundle()
compared = versus_baseline(pd.DataFrame(bundle["summaries"]))
forward = all_forward_nodes(bundle)

st.title("Parallel futures")
st.caption(scenario_line(bundle["scenario"]))
st.write(
    "All three policies start from the same inventory, face the same requested demand, and use the same seed. "
    "Do nothing stays on primary lanes. Alternative sourcing may use a reserve lane only after a primary lane cannot fill. "
    "Redistribution may move surplus on a lateral lane only after the donor keeps one day of expected outflow."
)

show = compared[
    [
        "policy_label",
        "unmet_demand_crates",
        "unmet_vs_do_nothing",
        "stockout_events",
        "events_vs_do_nothing",
        "service_level",
        "recovery_status",
        "estimated_spoilage_crates",
        "spoilage_vs_do_nothing",
        "transport_cost_units",
        "cost_vs_do_nothing",
    ]
].copy()
show["service_level"] = show["service_level"].map(fmt_pct)
show = show.rename(
    columns={
        "policy_label": "Policy",
        "unmet_demand_crates": "Unmet crates",
        "unmet_vs_do_nothing": "Unmet vs do nothing",
        "stockout_events": "Stockout events",
        "events_vs_do_nothing": "Events vs do nothing",
        "service_level": "Service level",
        "recovery_status": "Recovery",
        "estimated_spoilage_crates": "Estimated spoilage",
        "spoilage_vs_do_nothing": "Spoilage vs do nothing",
        "transport_cost_units": "Transport cost",
        "cost_vs_do_nothing": "Cost vs do nothing",
    }
)
st.dataframe(show, width="stretch", hide_index=True)
st.caption("A negative difference means less than do nothing. Spoilage is estimated. Cost is in synthetic units, not rupees.")
st.plotly_chart(metric_bars(compared), width="stretch")

st.subheader("Trade-offs")
st.write(bundle["recommendation"])
for policy, notes in bundle["movement"].items():
    label = compared.loc[compared["policy"] == policy, "policy_label"].iloc[0]
    with st.expander(f"{label} — why a move was or was not made"):
        for line in bundle["feasibility"][policy] + notes:
            st.write(line)

st.subheader("Stock at one counter")
retailers = sorted(forward.loc[forward["type"] == "retailer", "node_id"].unique())
if not retailers:
    st.caption("This run has no retailer stock series to plot.")
else:
    pick, crop = st.columns(2)
    with pick:
        node = st.selectbox("Location", retailers, index=retailers.index("RET-DEL") if "RET-DEL" in retailers else 0)
    with crop:
        sku = st.selectbox("Crop", ["tomato", "onion", "potato"])
    series = forward.loc[(forward["node_id"] == node) & (forward["sku"] == sku)]
    if series.empty:
        st.caption(f"No end-of-day stock was recorded for {node} {sku}.")
    else:
        st.plotly_chart(stock_trajectories(forward, node, sku), width="stretch")
        st.caption("Each line is end-of-day on-hand stock. A crate shipped out of one node is not still counted there.")

st.download_button(
    "Download comparison",
    data=csv_bytes(compared),
    file_name="echo_policy_comparison.csv",
    mime="text/csv",
    icon=":material/download:",
)
