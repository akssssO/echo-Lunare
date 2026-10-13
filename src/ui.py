"""Small Streamlit helpers shared by every page."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st


def apply_look() -> None:
    """Depth, type, and the sage / champagne palette. Native theme covers the base colours."""
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
          background:
            radial-gradient(900px 420px at 8% -10%, rgba(140, 207, 192, 0.16), transparent 55%),
            radial-gradient(700px 380px at 100% 0%, rgba(214, 197, 165, 0.10), transparent 50%),
            #172321;
          color: #E7E2D6;
          font-family: "Segoe UI", "Avenir Next", "Trebuchet MS", sans-serif;
        }
        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #31483f 0%, #1c2e28 100%);
          border-right: 1px solid rgba(214, 197, 165, 0.16);
          box-shadow: 12px 0 28px rgba(8, 12, 10, 0.28);
        }
        [data-testid="stIconMaterial"],
        [data-testid="stIconMaterial"] span,
        .material-symbols-rounded,
        span[translate="no"] {
          font-family: "Material Symbols Rounded" !important;
          font-weight: normal !important;
          letter-spacing: normal !important;
        }
        h1, h2, h3, [data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
          font-family: Palatino, "Palatino Linotype", "Iowan Old Style", Georgia, serif !important;
          color: #D6C5A5 !important;
          font-weight: 500 !important;
          letter-spacing: -0.02em;
        }
        [data-testid="stCaptionContainer"] { color: #B6C9A8; }
        [data-testid="stMetric"] {
          background: linear-gradient(165deg, #355246 0%, #263B34 52%, #1b2c27 100%);
          border: 1px solid rgba(214, 197, 165, 0.22) !important;
          border-radius: 18px !important;
          box-shadow:
            0 16px 28px rgba(8, 12, 10, 0.32),
            inset 0 1px 0 rgba(214, 197, 165, 0.28);
          padding: 0.4rem 0.2rem;
        }
        [data-testid="stMetricLabel"] { color: #B6C9A8 !important; }
        [data-testid="stMetricValue"] {
          font-family: Palatino, "Palatino Linotype", Georgia, serif;
          color: #E7E2D6 !important;
        }
        [data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {
          background: linear-gradient(180deg, #243832 0%, #1b2c27 100%);
          border: 1px solid rgba(182, 201, 168, 0.16);
          border-radius: 18px;
          box-shadow: 0 18px 32px rgba(8, 12, 10, 0.28), inset 0 1px 0 rgba(214, 197, 165, 0.12);
          padding: 0.35rem;
          overflow: hidden;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
          background: linear-gradient(180deg, #2c453c 0%, #263B34 100%);
          border-radius: 18px !important;
          box-shadow: 0 12px 24px rgba(8, 12, 10, 0.22), inset 0 1px 0 rgba(214, 197, 165, 0.16);
        }
        button[kind="primary"] {
          box-shadow: 0 8px 16px rgba(8, 12, 10, 0.28);
          border-radius: 12px;
        }
        [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
          box-shadow: 0 4px 10px rgba(8, 12, 10, 0.35);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.fragment(run_every=1.15)
def playback_clock() -> None:
    """Step the morning forward so a recording can walk through a finished run."""
    if not st.session_state.get("playing"):
        return
    now = time.monotonic()
    last = float(st.session_state.get("_play_tick", 0.0))
    if now - last < 0.9:
        return
    horizon = max(int(st.session_state.get("horizon", 14)), 1)
    current = int(st.session_state.get("as_of_day", 0))
    st.session_state.as_of_day = (current + 1) % horizon
    st.session_state._play_tick = now
    st.rerun()


def arm_playback() -> None:
    if st.session_state.get("playing"):
        st.session_state._play_tick = time.monotonic()


def require_bundle() -> dict[str, Any]:
    error = st.session_state.get("error")
    bundle = st.session_state.get("bundle")
    if error and bundle is None:
        st.caption("The simulation did not finish. Set the end day after the start day, then change any control to try again.")
        st.caption(error)
        st.stop()
    if bundle is None:
        st.caption("The first run is still settling. If this stays empty, press Run simulation in the sidebar.")
        st.stop()
    return bundle


def scenario_line(scenario) -> str:
    if scenario.kind == "none":
        shock = "No shock is applied. This is the reference case."
    elif scenario.kind == "capacity_loss":
        shock = (
            f"{scenario.supplier_id} keeps {scenario.capacity_factor * 100:.0f}% of normal production "
            f"on days {scenario.start_day}–{scenario.end_day - 1}."
        )
    elif scenario.kind == "demand_surge":
        nodes = "all retailers" if not scenario.demand_node_ids else ", ".join(scenario.demand_node_ids)
        shock = (
            f"Requested demand at {nodes} is multiplied by {scenario.demand_factor:.1f} "
            f"on days {scenario.start_day}–{scenario.end_day - 1}."
        )
    else:
        shock = (
            f"{scenario.route_id} takes {scenario.extra_lead_days} extra "
            f"{'day' if scenario.extra_lead_days == 1 else 'days'} "
            f"on days {scenario.start_day}–{scenario.end_day - 1}."
        )
    return f"{scenario.name}. Seed {scenario.seed}. Horizon {scenario.horizon} days. {shock}"


def versus_baseline(summaries: pd.DataFrame) -> pd.DataFrame:
    """Differences against the do-nothing row of the same run."""
    frame = summaries.copy()
    base = frame.loc[frame["policy"] == "do_nothing"].iloc[0]
    frame["unmet_vs_do_nothing"] = (frame["unmet_demand_crates"] - base["unmet_demand_crates"]).round(1)
    frame["events_vs_do_nothing"] = frame["stockout_events"] - base["stockout_events"]
    frame["spoilage_vs_do_nothing"] = (frame["estimated_spoilage_crates"] - base["estimated_spoilage_crates"]).round(1)
    frame["cost_vs_do_nothing"] = (frame["transport_cost_units"] - base["transport_cost_units"]).round(1)
    return frame


def as_of_day(horizon: int) -> int:
    horizon = max(int(horizon), 1)
    st.session_state.setdefault("as_of_day", min(3, horizon - 1))
    if int(st.session_state.as_of_day) > horizon - 1:
        st.session_state.as_of_day = horizon - 1
    return int(
        st.slider(
            "As-of morning",
            min_value=0,
            max_value=horizon - 1,
            help="Shows the risk assessment computed on that morning, before that day's demand is served.",
            key="as_of_day",
        )
    )


def fmt_pct(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "undefined"
    return f"{float(value) * 100:.1f}%"


def fmt_num(value: Any, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "undefined"
    return f"{float(value):,.{digits}f}"


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")
