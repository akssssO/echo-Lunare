"""Physical constraints of the synthetic inventory engine."""

import pandas as pd

from src.data_generator import generate_demand_plan
from src.network import build_network, validate_network
from src.scenario import Scenario, preset_scenario
from src.simulation import assert_constraints, simulate


def _run(kind: str = "none", policy: str = "do_nothing", seed: int = 42, horizon: int = 10):
    net = build_network()
    scenario = preset_scenario(kind, seed=seed, horizon=horizon)
    scenario.history_days = 5
    plan = generate_demand_plan(net, scenario)
    result = simulate(net, scenario, policy, plan)
    assert_constraints(net, result)
    return net, scenario, plan, result


def test_reference_network_is_valid():
    net = build_network()
    validate_network(net)
    assert len(net.nodes) >= 12
    assert any(edge.role == "alternate" for edge in net.edges.values())
    assert any(edge.role == "lateral" for edge in net.edges.values())


def test_demand_plan_is_deterministic_and_seed_sensitive():
    net = build_network()
    left = generate_demand_plan(net, preset_scenario("none", seed=1, horizon=8))
    again = generate_demand_plan(net, preset_scenario("none", seed=1, horizon=8))
    other = generate_demand_plan(net, preset_scenario("none", seed=2, horizon=8))
    assert left == again
    assert left != other


def test_stock_is_conserved_and_nonnegative():
    _net, _scenario, _plan, result = _run("capacity_loss", "alternate_sourcing")
    assert abs(result.ledger["imbalance"]) < 1e-6
    assert (result.node_days["on_hand"] >= -1e-6).all()


def test_shipments_respect_lead_time_and_route_capacity():
    net, _scenario, _plan, result = _run("transport_delay", "alternate_sourcing", horizon=12)
    ships = result.shipments
    assert not ships.empty
    assert (ships["arrival_day"] == ships["day"] + ships["lead_time_days"]).all()
    delayed = ships.loc[(ships["edge_id"] == "E-NGP-DEL") & (ships["day"].between(1, 11))]
    assert not delayed.empty
    assert (delayed["lead_time_days"] >= 6).all()
    grouped = ships.groupby(["day", "edge_id"])["crates"].sum()
    for (day, edge_id), qty in grouped.items():
        assert qty <= net.edges[edge_id].capacity_per_day + 1e-6


def test_supplier_capacity_is_enforced_during_a_loss():
    _net, scenario, _plan, result = _run("capacity_loss", "do_nothing", horizon=8)
    log = result.production_log
    nashik = log.loc[(log["node_id"] == "SUP-NSK") & (log["sku"] == "tomato") & (log["day"] >= 0)]
    assert not nashik.empty
    disrupted = nashik.loc[nashik["day"].between(scenario.start_day, scenario.end_day - 1)]
    normal_cap = 460.0
    assert (disrupted["crates"] <= normal_cap * scenario.capacity_factor + 1e-6).all()
    assert (disrupted["capacity_limit"] <= normal_cap * scenario.capacity_factor + 1e-6).all()


def test_same_seed_replays_the_same_service_level():
    _net_a, _sc_a, _plan_a, first = _run("demand_surge", "do_nothing", seed=7)
    _net_b, _sc_b, _plan_b, second = _run("demand_surge", "do_nothing", seed=7)
    pd.testing.assert_frame_equal(first.daily_service, second.daily_service)


def test_alternate_sourcing_uses_a_real_alternate_lane_when_nashik_is_cut():
    _net, _scenario, _plan, result = _run("capacity_loss", "alternate_sourcing", horizon=12)
    forward = result.shipments.loc[result.shipments["day"] >= 0]
    used = set(forward.loc[forward["role"] == "alternate", "edge_id"])
    assert used
    assert used <= {"E-PUN-NGP", "E-PUN-BPL", "E-IDR-NGP", "E-IDR-BPL", "E-NSK-BPL", "E-BPL-DEL", "E-BPL-JAI", "E-NGP-LKO", "E-LKO-RAGR", "E-DEL-RGWL"}


def test_redistribution_does_not_ship_more_than_the_donor_held():
    net, _scenario, _plan, result = _run("transport_delay", "redistribute", horizon=12)
    lateral = result.shipments.loc[(result.shipments["role"] == "lateral") & (result.shipments["day"] >= 0)]
    assert not lateral.empty
    for row in lateral.itertuples(index=False):
        assert row.crates > 0
        assert row.edge_id in net.edges
        assert net.edges[row.edge_id].role == "lateral"


def test_do_nothing_never_uses_alternate_or_lateral_lanes():
    _net, _scenario, _plan, result = _run("transport_delay", "do_nothing", horizon=8)
    forward = result.shipments.loc[result.shipments["day"] >= 0]
    assert set(forward["role"].unique()) <= {"primary"}


def test_undisrupted_reference_case_meets_demand():
    _net, _scenario, _plan, result = _run("none", "do_nothing", horizon=10)
    retail = result.forward(result.node_days)
    retail = retail.loc[retail["type"] == "retailer"]
    assert float(retail["unmet_demand"].sum()) == 0.0


def test_requested_demand_is_kept_when_sales_are_short():
    """A stockout must not be written back as a drop in requested demand."""
    _net, _scenario, plan, result = _run("demand_surge", "do_nothing", horizon=12)
    forward = result.forward(result.node_days)
    short = forward.loc[(forward["type"] == "retailer") & (forward["unmet_demand"] > 0.5)]
    assert not short.empty
    for row in short.head(8).itertuples(index=False):
        planned = plan[(row.node_id, row.sku, int(row.day))]
        assert abs(row.requested_demand - planned) < 1e-6
        assert abs((row.served + row.unmet_demand) - row.requested_demand) < 1e-3


def test_delay_interventions_are_not_identical():
    net = build_network()
    scenario = Scenario(
        name="delay",
        kind="transport_delay",
        route_id="E-NGP-DEL",
        extra_lead_days=4,
        seed=42,
        horizon=12,
        history_days=4,
        start_day=1,
        end_day=10,
    )
    plan = generate_demand_plan(net, scenario)
    base = simulate(net, scenario, "do_nothing", plan)
    alt = simulate(net, scenario, "alternate_sourcing", plan)
    share = simulate(net, scenario, "redistribute", plan)
    for result in (base, alt, share):
        assert_constraints(net, result)
    base_unmet = float(base.forward(base.node_days)["unmet_demand"].sum())
    alt_unmet = float(alt.forward(alt.node_days)["unmet_demand"].sum())
    share_unmet = float(share.forward(share.node_days)["unmet_demand"].sum())
    assert alt_unmet < base_unmet
    assert share_unmet < base_unmet
    assert alt_unmet != share_unmet
