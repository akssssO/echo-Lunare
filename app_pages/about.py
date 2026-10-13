import streamlit as st

from src.assumptions import ASSUMPTIONS

st.title("About and limitations")
st.caption("This is a synthetic demo. It is not connected to a live supply chain, and the place names are labels, not contracts.")

st.markdown(
    """
### Why this exists

Food moves through a chain of growers, consolidation sheds, night hubs, and city counters.
A shortage at a counter is often the last visible sign of a problem that started days earlier:
a grower desk that could not load, a lane that slowed, or a demand spike at one city.
ECHO — Every Shortage Leaves a Signal — is a public-good prototype for seeing that signal
while there is still time to compare a few feasible responses.

It is built for people who plan replenishment, not for autonomous control of trucks or markets.
The intended beneficiaries of a future validated system would be public distribution planners,
farmer-producer organisations, and city market managers who need a shared, inspectable picture
of where stock is thinning. This demo does not serve those users with live data.

### What is implemented

The app generates a synthetic regional network, simulates inventory forward under a shock,
scores risk from information available that morning, and compares three advisory policies:
do nothing, alternative sourcing, and inventory redistribution. An evaluation page replays
held-out synthetic scenarios against a simple cover threshold. Every control that claims to
change the scenario does so when you press Run simulation.

### What is not implemented

There is no live feed, no government dataset, no retailer integration, and no claim of measured
social impact. Place names such as Nashik, Nagpur, and Chandni Chowk are geographic labels on
a fictional graph. They are not statements about those markets.

### Responsible use

Do not use these outputs to dispatch real vehicles, reject a supplier, or brief the public
as if they were observations. Recommendations are comparisons inside a model. A real deployment
would need data-sharing agreements, a check that the graph matches actual lanes, and a review
by the people who would bear a wrong call.

### What real-world validation would require

- Inventory, requested demand, and delivery logs from participating organisations, with permission.
- A confirmed lane list, including which alternate suppliers can actually load a given crop.
- A spoilage study. The percentages in this model are assumptions.
- A prospective test: alerts issued with only past data, then compared with later stockouts.
- A review of who is harmed if an alert is wrong, including farmers asked to hold or divert stock.
- An operating owner. This repository does not provide one.

### Open source

ECHO is meant to be small enough to read. The simulation, risk weights, and evaluation rules
live in `src/` and are covered by tests. Team Lunaré, led by Akshadha Saxena, prepared this
prototype for Commit for Good Round 2. No deployment URL is claimed.
    """
)

st.subheader("Modelling assumptions")
for item in ASSUMPTIONS:
    st.write("• " + item)
