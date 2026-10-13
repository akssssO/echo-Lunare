"""Print synthetic scenario summaries. Not part of the app."""

from src.interventions import compare, recommendation, summarize_result
from src.network import build_network
from src.scenario import default_scenario, preset_scenario
from src.simulation import assert_constraints

net = build_network()
for name in ("none", "capacity_loss", "demand_surge", "transport_delay"):
    scenario = preset_scenario(name, seed=42, horizon=14)
    results = compare(net, scenario)
    print("\n==", scenario.name, "==")
    summaries = []
    for policy, result in results.items():
        assert_constraints(net, result)
        summary = summarize_result(result)
        summaries.append(summary)
        alerts = result.forward(result.risk)
        retail_alerts = alerts[(alerts.type == "retailer") & (alerts.echo_alert)]
        print(
            f"{policy:22} unmet={summary['unmet_demand_crates']:8.1f} "
            f"svc={summary['service_level']} events={summary['stockout_events']:3} "
            f"spoil={summary['estimated_spoilage_crates']:7.1f} cost={summary['transport_cost_units']:8.1f} "
            f"recovery={summary['recovery_status']} retail_alert_rows={len(retail_alerts)}"
        )
    print(recommendation(summaries)[:400])

scenario = default_scenario()
result = compare(net, scenario)["do_nothing"]
risk = result.forward(result.risk)
print("\nDefault risk levels", risk.groupby("risk_level").size().to_dict())
print("ledger", result.ledger)
