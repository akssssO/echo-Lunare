# ECHO — Every Shortage Leaves a Signal

ECHO is a synthetic decision-support prototype for resilient food distribution. It flags locations whose stock may not last until replenishment, shows how a shock travels through an illustrative Indian fresh-produce network, and compares three advisory responses before the shortage spreads.

**DEMO MODE — Synthetic data; not connected to live supply chains.**

Place names (Nashik, Nagpur, Delhi, and others) are labels on a fictional graph. They are not measurements of real mandis, contracts, or freight lanes. Team Lunaré, led by Akshadha Saxena, built this for Commit for Good Round 2.

## Problem

A city counter runs out after the cause has already moved through growers, sheds, and hubs. Planners often see the empty shelf, not the earlier signal, and they rarely get to compare “do nothing”, “buy from the reserve supplier”, and “rebalance stock” on the same facts.

## What the prototype does

- Builds a directed network of suppliers, warehouses, hubs, and retailers for tomatoes, onions, and potatoes.
- Simulates daily inventory, lost sales, assumed spoilage, route capacity, and supplier capacity.
- Scores risk from that morning’s stock, pipeline, trailing **requested** demand, lead time, and upstream capacity. Sales during a stockout are not treated as low demand.
- Compares do nothing, alternative sourcing, and inventory redistribution on one shared demand path and seed.
- Evaluates the alert rule against a 2-day cover threshold on held-out synthetic scenarios. Undefined precision, recall, or F1 stay undefined.
- Exports the generated tables as CSV.

Recommendations are advisory. The app does not dispatch vehicles or place orders.

## Architecture

```text
app.py                         Streamlit shell, scenario controls, navigation
app_pages/                     One file per section
src/data_generator.py          Seeded demand paths and catalogue tables
src/network.py                 Synthetic graph, capacities, opening stock
src/risk_engine.py             Fixed-weight score and alert rule
src/simulation.py              Daily inventory engine
src/interventions.py           Heuristics, propagation, recommendation text
src/evaluation.py              Held-out scenarios and sklearn metrics
```

The generator does not step inventory. The simulator does not draw random numbers itself; it consumes the demand plan for the chosen seed.

## Simulation assumptions

- One day per step. One crate is the unit (illustratively about 20 kg). Costs are synthetic units, not rupees.
- Unmet demand is lost, not backlogged.
- A shipment sent at the end of day *t* arrives at the start of day *t + lead time*.
- Production, route capacity, storage, and on-hand stock are hard limits. Inventory cannot go negative.
- Spoilage is an assumed daily fraction of **hub and retailer** on-hand stock only: tomato 2%, onion 0.8%, potato 0.3%. It is an estimate, not weighed waste.
- Risk weights are fixed, not fit on the test scenarios: cover 0.50, delay 0.20, demand deviation 0.15, upstream capacity 0.15. An alert fires on a hard cover shortfall or when the score reaches 0.40.
- The baseline used in evaluation flags on-hand cover below 2 days and ignores pipeline, delay, and supplier capacity.
- Alternative sourcing uses an alternate lane only after primary lanes cannot fill, and only when the source has stock and the route has capacity.
- Redistribution keeps 1.0 day of expected outflow at the donor (0.35 days in the aggressive stress policy) and never counts the same crates twice.
- A warm-up window illustrates requested demand. The forward run restarts from the documented opening inventory so that warm-up stock is not counted twice.
- Downstream reachability is exposure, not a prediction that the node will stock out. Predicted shortages come only from the inventory simulation.

## Setup

Python 3.12 was used to develop this prototype. Python 3.11 should also work.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```


## Tests

```bash
pytest -q
```

The tests cover deterministic demand, graph connectivity, nonnegative inventory, stock conservation, delivery timing, supplier and route limits, intervention feasibility, stable risk scores, undefined metrics, and a full replay of the held-out suite.


## Limitations

- The network, demand, and disruptions are synthetic.
- Spoilage, travel times, and costs are assumptions.
- The heuristics are not an optimiser and can make a scenario worse. The evaluation is there to show that, not to hide it.
- A real pilot needs permissioned operational data, a lane list that operators recognise, a prospective alert test, and a named operating owner.

## Contributing

Open an issue or pull request. Please keep new behaviour deterministic and covered by a test, and do not describe synthetic output as field data.

## License

MIT is the recommended license. See `LICENSE`.
