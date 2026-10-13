# Round 2 demo and submission notes

Team Lunaré. Team leader: Akshadha Saxena.
ECHO — Every Shortage Leaves a Signal.

Do not read out a GitHub URL or a live URL unless the team has actually published them.
The app is a local Streamlit prototype. Results are synthetic.

## 60–90 second video script

**0:00–0:12.** “ECHO stands for Every Shortage Leaves a Signal. Fresh-produce shortages show up at the counter, but the cause usually started earlier: a supplier that could not load, or a lane that slowed. This is a synthetic demo, not a live Indian supply chain.”

**0:12–0:28.** Show the banner and the executive overview. “The default shock delays the Nagpur–Delhi lane. Do-nothing service drops, and the timeline shows lost sales building over the next days. The recommendation is advisory. It ranks the policies this run actually computed.”

**0:28–0:48.** Open Supply network, then Early-warning. “Red means the inventory simulation predicts unmet demand. Tan only means the node is downstream. Exposure is not failure. The warning for each retailer uses stock, trailing requested demand, lead time, and upstream capacity. It does not treat a stockout’s low sales as low demand.”

**0:48–1:15.** Open Parallel futures. “Same seed, same demand, three policies. Alternative sourcing cuts more of the lost sales and costs more, because reserve lanes are priced higher. Redistribution helps less, and it can increase the number of separate stockout spells. Doing nothing remains the reference.”

**1:15–1:30.** Open Evaluation. “We score ECHO against a two-day cover threshold on held-out synthetic scenarios. Where there is no shortage, recall is undefined. We do not claim a field result or that ECHO always wins.”

## Three-minute judging flow

1. **20 seconds.** State the public-good problem and point at the demo-mode banner. Say the network is illustrative.
2. **40 seconds.** Executive overview. Read service level, unmet demand, and the recommendation sentence. Point at the timeline.
3. **40 seconds.** Supply network. Hover one delayed lane and one downstream node. Read one line of the accessible table so the chart is not the only evidence.
4. **40 seconds.** Early-warning. Pick a flagged retailer. Read the explanation: cover, lead time, and which feature contributed.
5. **30 seconds.** Disruption lab. Change the preset to supplier capacity loss, press Run simulation, and show that the KPIs move.
6. **40 seconds.** Parallel futures. Compare unmet demand, stockout events, spoilage, and transport cost. Say which policy was worse on at least one metric if the table shows it.
7. **20 seconds.** Evaluation. Show one row where a metric is undefined, and one operating comparison. Do not claim a universal improvement.
8. **10 seconds.** About. Name the validation still required: permissioned data, a real lane list, a prospective test, and an operating owner.

## Submission checklist

- [ ] `pytest -q` passes on a clean environment.
- [ ] `streamlit run app.py` opens and the default scenario renders without an error banner.
- [ ] Run simulation, reset, compare, and CSV download have each been clicked once.
- [ ] Held-out evaluation has been run in the app and the table matches `pytest`, not a hand-typed score.
- [ ] Screenshots were taken from this build.
- [ ] README setup matches the commands you actually used.
- [ ] GitHub repository URL added only after the push succeeds.
- [ ] Streamlit Cloud URL added only after the deploy succeeds.
- [ ] Slides use the computed evaluation table. Undefined metrics stay “undefined”.
- [ ] Team slide lists Lunaré and Akshadha Saxena. Add other members only if they are on the team.
- [ ] No slide says the model was deployed, piloted, or measured in the field.

## Slide outline

The file `docs/ECHO_round2.pptx` is generated from `tools/build_slides.py` after a local evaluation run. Rebuild it if the simulator changes. Slide 8 leaves GitHub and live URLs blank on purpose.
