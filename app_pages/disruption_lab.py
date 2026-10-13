import streamlit as st

from src.network import build_network
from src.ui import require_bundle, scenario_line

bundle = require_bundle()
network = build_network()

st.title("Disruption lab")
st.caption("Let go of a control and the simulation follows. Reset in the sidebar restores the Nagpur–Delhi delay, seed 42, and a 14-day horizon.")

suppliers = sorted(node.node_id for node in network.nodes.values() if node.node_type == "supplier")
routes = sorted(network.edges)
retailers = sorted(node.node_id for node in network.nodes.values() if node.node_type == "retailer")

st.selectbox(
    "Shock",
    options=["transport_delay", "capacity_loss", "demand_surge", "none"],
    format_func=lambda key: {
        "transport_delay": "Transport delay",
        "capacity_loss": "Supplier capacity loss",
        "demand_surge": "Demand surge",
        "none": "No disruption",
    }[key],
    key="kind",
)
left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True):
        st.markdown("**Capacity and delay**")
        st.selectbox("Supplier", options=suppliers, key="supplier_id", help="Used when the shock is a capacity loss.")
        st.slider("Supplier capacity reduction (%)", min_value=0, max_value=100, key="capacity_loss_pct", help="80 means the supplier keeps 20% of normal production.")
        st.selectbox("Route", options=routes, key="route_id", help="Used when the shock is a transport delay.")
        st.slider("Extra lead time (days)", min_value=0, max_value=7, key="extra_lead_days")
with right:
    with st.container(border=True):
        st.markdown("**Demand and window**")
        st.slider("Demand multiplier", min_value=1.0, max_value=3.0, step=0.1, key="demand_factor", help="Applied only to the retailers selected below, and only for a demand surge.")
        st.multiselect("Retailers in a demand surge", options=retailers, key="demand_nodes")
        start, end = st.columns(2)
        with start:
            st.number_input("Start day", min_value=0, max_value=20, step=1, key="start_day")
        with end:
            st.number_input("End day (exclusive)", min_value=1, max_value=21, step=1, key="end_day")

st.subheader("What this run used")
scenario = bundle["scenario"]
st.caption(scenario_line(scenario))
st.dataframe(bundle["events"], width="stretch", hide_index=True)
st.caption(
    f"On screen now: {scenario.name}, seed {scenario.seed}, horizon {scenario.horizon} days, "
    f"shock on days {scenario.start_day} to {scenario.end_day - 1}."
)

st.markdown(
    """
**How each shock is applied**

- **Capacity loss** multiplies the selected supplier's daily production for every crop it makes. Stock already on hand can still be shipped.
- **Demand surge** multiplies requested demand at the selected retailers. Other retailers keep their normal synthetic demand.
- **Transport delay** adds days to the selected lane's lead time for shipments dispatched inside the window. Trucks already booked keep their original arrival.
- **No disruption** runs the same replenishment rules with the shock switched off, so it is the reference case.
    """
)
