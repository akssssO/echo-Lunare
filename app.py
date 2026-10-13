"""ECHO — Every Shortage Leaves a Signal."""

from __future__ import annotations

import streamlit as st

from src.app_services import execute
from src.scenario import Scenario
from src.ui import apply_look, arm_playback, playback_clock

st.set_page_config(
    page_title="ECHO — Every Shortage Leaves a Signal",
    page_icon=":material/crisis_alert:",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULTS = {
    "preset": "transport_delay",
    "kind": "transport_delay",
    "supplier_id": "SUP-NSK",
    "route_id": "E-NGP-DEL",
    "capacity_loss_pct": 80,
    "demand_factor": 1.9,
    "extra_lead_days": 4,
    "start_day": 1,
    "end_day": 12,
    "seed": 42,
    "horizon": 14,
    "demand_nodes": ["RET-DEL", "RET-NOI"],
}

PRESETS = {
    "transport_delay": {
        "kind": "transport_delay",
        "route_id": "E-NGP-DEL",
        "extra_lead_days": 4,
        "supplier_id": "SUP-NSK",
        "capacity_loss_pct": 80,
        "demand_factor": 1.9,
        "demand_nodes": ["RET-DEL", "RET-NOI"],
        "start_day": 1,
        "end_day": 12,
    },
    "capacity_loss": {
        "kind": "capacity_loss",
        "supplier_id": "SUP-NSK",
        "capacity_loss_pct": 80,
        "route_id": "E-NGP-DEL",
        "extra_lead_days": 4,
        "demand_factor": 1.9,
        "demand_nodes": ["RET-DEL", "RET-NOI"],
        "start_day": 1,
        "end_day": 12,
    },
    "demand_surge": {
        "kind": "demand_surge",
        "demand_factor": 1.9,
        "demand_nodes": ["RET-DEL", "RET-NOI"],
        "supplier_id": "SUP-NSK",
        "capacity_loss_pct": 80,
        "route_id": "E-NGP-DEL",
        "extra_lead_days": 4,
        "start_day": 1,
        "end_day": 12,
    },
    "none": {
        "kind": "none",
        "supplier_id": "SUP-NSK",
        "capacity_loss_pct": 0,
        "route_id": "E-NGP-DEL",
        "extra_lead_days": 0,
        "demand_factor": 1.0,
        "demand_nodes": ["RET-DEL", "RET-NOI"],
        "start_day": 0,
        "end_day": 14,
    },
}


def _init() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("force_run", False)
    st.session_state.setdefault("error", None)


def _apply_preset() -> None:
    for key, value in PRESETS[st.session_state.preset].items():
        st.session_state[key] = value


def _reset() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state.force_run = True
    st.session_state.error = None


def _signature() -> tuple:
    nodes = tuple(st.session_state.demand_nodes)
    return (
        st.session_state.kind,
        st.session_state.supplier_id,
        st.session_state.route_id,
        int(st.session_state.capacity_loss_pct),
        float(st.session_state.demand_factor),
        int(st.session_state.extra_lead_days),
        int(st.session_state.start_day),
        int(st.session_state.end_day),
        int(st.session_state.seed),
        int(st.session_state.horizon),
        nodes,
    )


def scenario_from_state() -> Scenario:
    horizon = max(4, int(st.session_state.horizon))
    start = min(max(0, int(st.session_state.start_day)), horizon - 1)
    end = min(horizon, max(start + 1, int(st.session_state.end_day)))
    kind = st.session_state.kind
    names = {
        "none": "No disruption",
        "capacity_loss": "Supplier capacity loss",
        "demand_surge": "Demand surge",
        "transport_delay": "Transport delay",
    }
    return Scenario(
        name=names[kind],
        kind=kind,
        seed=int(st.session_state.seed),
        horizon=horizon,
        history_days=14,
        supplier_id=st.session_state.supplier_id,
        route_id=st.session_state.route_id,
        capacity_factor=1.0 - (int(st.session_state.capacity_loss_pct) / 100.0),
        demand_factor=float(st.session_state.demand_factor),
        extra_lead_days=int(st.session_state.extra_lead_days),
        start_day=start,
        end_day=end,
        demand_node_ids=tuple(st.session_state.demand_nodes),
    )


def _run() -> None:
    try:
        bundle = execute(scenario_from_state())
    except Exception as exc:  # shown to the operator; the engines also raise on broken physics
        st.session_state.bundle = None
        st.session_state.error = f"{type(exc).__name__}: {exc}"
        return
    st.session_state.bundle = bundle
    st.session_state.error = None
    st.session_state.signature = _signature()


_init()

with st.sidebar:
    st.markdown("### ECHO")
    st.caption("Every Shortage Leaves a Signal")
    st.caption("Team Lunaré · synthetic demo")
    st.segmented_control(
        "Scenario preset",
        options=["transport_delay", "capacity_loss", "demand_surge", "none"],
        format_func=lambda key: {
            "transport_delay": "Transport delay",
            "capacity_loss": "Capacity loss",
            "demand_surge": "Demand surge",
            "none": "No disruption",
        }[key],
        key="preset",
        on_change=_apply_preset,
        width="stretch",
    )
    st.number_input("Random seed", min_value=0, max_value=99999, step=1, key="seed")
    st.slider("Horizon (days)", min_value=7, max_value=21, key="horizon")
    run_clicked = st.button("Run simulation", type="primary", width="stretch", icon=":material/play_arrow:")
    st.button("Reset scenario", on_click=_reset, width="stretch", icon=":material/restart_alt:")
    st.toggle(
        "Play mornings",
        key="playing",
        on_change=arm_playback,
        help="Walks the as-of morning through this finished run, about once a second. Useful while you record. The figures stay on the same simulation.",
    )
    if st.button("Compare interventions", width="stretch", icon=":material/alt_route:"):
        st.switch_page("app_pages/futures.py")
    st.caption("Changing a preset, the seed, or the horizon reruns the simulation. Shock details live in Disruption lab.")

needs_run = (
    run_clicked
    or st.session_state.get("bundle") is None
    or st.session_state.pop("force_run", False)
    or st.session_state.get("signature") != _signature()
)
if needs_run:
    with st.spinner("Simulating inventory, risk, and the three policies…"):
        _run()

apply_look()
playback_clock()

navigation = st.navigation(
    [
        st.Page("app_pages/overview.py", title="Executive overview", icon=":material/monitoring:"),
        st.Page("app_pages/network_page.py", title="Supply network", icon=":material/hub:"),
        st.Page("app_pages/early_warning.py", title="Early-warning engine", icon=":material/crisis_alert:"),
        st.Page("app_pages/disruption_lab.py", title="Disruption lab", icon=":material/science:"),
        st.Page("app_pages/futures.py", title="Parallel futures", icon=":material/alt_route:"),
        st.Page("app_pages/audit.py", title="Explainability and audit", icon=":material/fact_check:"),
        st.Page("app_pages/evaluation.py", title="Evaluation", icon=":material/rule:"),
        st.Page("app_pages/explorer.py", title="Data explorer", icon=":material/table:"),
        st.Page("app_pages/about.py", title="About and limitations", icon=":material/info:"),
    ],
    position="sidebar",
)
navigation.run()
