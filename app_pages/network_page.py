import streamlit as st

from src.figures import network_figure
from src.ui import as_of_day, require_bundle, scenario_line

bundle = require_bundle()
scenario = bundle["scenario"]
day = as_of_day(scenario.horizon)
risk = bundle["results"]["do_nothing"].forward(bundle["results"]["do_nothing"].risk)
morning = risk.loc[risk["day"] == day]
edge = scenario.route_id if scenario.kind == "transport_delay" else None
view = bundle["propagation"].sort_values(
    ["predicted_shortage", "relationship", "node_id"], ascending=[False, True, True]
)

st.title("Supply network")
st.caption(scenario_line(scenario))
st.caption(
    "Read left to right: suppliers, warehouses, hubs, retailers. "
    "Shape is the tier. Colour is the status. Hover a lane midpoint for lead time, capacity, and cost."
)

exposed = int((view["relationship"] == "downstream exposed").sum())
direct = int((view["relationship"] == "directly affected").sum())
failed = int(view["predicted_shortage"].sum())
with st.container(horizontal=True):
    st.metric("Directly affected", direct, border=True, help="The supplier, or the two ends of the delayed lane.")
    st.metric("Downstream exposed", exposed, border=True, help="Reachable downstream. Not a prediction of failure.")
    st.metric("Predicted shortages", failed, border=True, help="Nodes whose do-nothing run records unmet demand.")

st.plotly_chart(
    network_figure(bundle["network"], bundle["propagation"], morning, edge),
    width="stretch",
)
st.caption(
    "Diamond supplier, square warehouse, hexagon hub, circle retailer. "
    "Solid lines are primary lanes, teal dashes are alternate lanes, champagne dots are lateral lanes. "
    "The coral line is the delayed route, when this scenario delays one. "
    "Coral nodes later show unmet demand. Warm nodes are directly affected. Champagne nodes are only exposed."
)

st.subheader("Accessible summary")
if scenario.kind == "none":
    st.caption("No shock is active, so no location is marked directly affected or downstream-exposed.")
table = view[
    ["node_id", "name", "type", "place_label", "relationship", "predicted_shortage", "simulated_unmet_crates"]
].rename(
    columns={
        "node_id": "ID",
        "name": "Name",
        "type": "Type",
        "place_label": "Place",
        "relationship": "Relationship to the shock",
        "predicted_shortage": "Predicted shortage",
        "simulated_unmet_crates": "Simulated unmet crates",
    }
)
st.dataframe(table, width="stretch", hide_index=True)
st.caption(
    f"{exposed} locations are downstream-exposed. {failed} locations show simulated unmet demand under do nothing. "
    "Exposure is not a prediction of failure."
)
