"""Plotly figures. Colours follow the sage panel and champagne type."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.network import SupplyNetwork
from src.simulation import POLICY_LABELS

PAPER = "#1B2C27"
INK = "#E7E2D6"
MUTED = "#B6C9A8"
GRID = "#314840"
DATA = "#8CCFC0"
CHAMPAGNE = "#D6C5A5"
RISK = "#E99A88"
SAGE = "#B6C9A8"
TYPE_COLOR = {
    "supplier": DATA,
    "warehouse": "#9BC7BB",
    "hub": CHAMPAGNE,
    "retailer": "#E7E2D6",
}
TYPE_SYMBOL = {
    "supplier": "diamond",
    "warehouse": "square",
    "hub": "hexagon",
    "retailer": "circle",
}
POLICY_COLOR = {
    "do_nothing": RISK,
    "alternate_sourcing": DATA,
    "redistribute": CHAMPAGNE,
    "Do nothing": RISK,
    "Alternative sourcing": DATA,
    "Inventory redistribution": CHAMPAGNE,
}
DISPLAY_ORDER = [
    "SUP-NSK",
    "SUP-LSG",
    "SUP-AGR",
    "SUP-IDR",
    "SUP-PUN",
    "WH-NGP",
    "WH-BPL",
    "HUB-DEL",
    "HUB-LKO",
    "HUB-JAI",
    "RET-DEL",
    "RET-NOI",
    "RET-AGR",
    "RET-KNP",
    "RET-JAI",
    "RET-GWL",
]


def _base(fig: go.Figure, title: str, height: int | None = None) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=INK)),
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font=dict(color=INK, family="Segoe UI, Palatino, sans-serif", size=13),
        legend=dict(orientation="h", yanchor="top", y=-0.22, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=12, color=SAGE)),
        margin=dict(l=64, r=24, t=56, b=78),
        hoverlabel=dict(bgcolor="#263B34", font_size=13, font_color=INK, bordercolor=CHAMPAGNE),
        height=height,
    )
    return fig


def service_timeline(
    daily_by_policy: dict[str, pd.DataFrame],
    shock_start: int | None = None,
    shock_end: int | None = None,
    show_shock: bool = True,
    mark_day: int | None = None,
) -> go.Figure:
    fig = go.Figure()
    if show_shock and shock_start is not None and shock_end is not None and shock_end > shock_start:
        fig.add_vrect(
            x0=shock_start - 0.5,
            x1=shock_end - 0.5,
            fillcolor="rgba(233, 154, 136, 0.16)",
            line_width=0,
        )
    if mark_day is not None:
        fig.add_vline(x=mark_day, line_width=1.4, line_dash="dot", line_color=CHAMPAGNE)
    for policy, frame in daily_by_policy.items():
        view = frame.loc[frame["day"] >= 0]
        fig.add_trace(
            go.Scatter(
                x=view["day"],
                y=view["unmet_demand"],
                mode="lines+markers",
                name=POLICY_LABELS.get(policy, policy),
                line=dict(color=POLICY_COLOR.get(policy, DATA), width=2.4),
                marker=dict(size=7),
                hovertemplate="Day %{x}<br>%{y:.1f} crates unmet<extra>" + POLICY_LABELS.get(policy, policy) + "</extra>",
            )
        )
    fig.update_xaxes(title="Forward day", gridcolor=GRID, zeroline=False, dtick=1)
    fig.update_yaxes(title="Simulated unmet demand (crates)", gridcolor=GRID, zeroline=False, rangemode="tozero")
    return _base(fig, "Lost sales by day — do nothing against the two interventions", height=420)


def stock_trajectories(frame: pd.DataFrame, node_id: str, sku: str) -> go.Figure:
    view = frame.loc[(frame["node_id"] == node_id) & (frame["sku"] == sku)]
    fig = go.Figure()
    if view.empty:
        fig.add_annotation(text="No stock series for this location and crop.", showarrow=False, font=dict(color=MUTED, size=14))
    for policy, group in view.groupby("policy"):
        fig.add_trace(
            go.Scatter(
                x=group["day"],
                y=group["on_hand"],
                mode="lines",
                name=str(policy),
                line=dict(color=POLICY_COLOR.get(str(policy), DATA), width=2.4),
                hovertemplate="Day %{x}<br>%{y:.1f} crates on hand<extra>" + str(policy) + "</extra>",
            )
        )
    fig.update_xaxes(title="Forward day", gridcolor=GRID, dtick=1)
    fig.update_yaxes(title="On-hand crates at end of day", gridcolor=GRID, rangemode="tozero")
    return _base(fig, f"End-of-day stock — {node_id}, {sku}", height=380)


def metric_bars(summaries: pd.DataFrame) -> go.Figure:
    ordered = summaries.copy()
    baseline = float(ordered.loc[ordered["policy"] == "do_nothing", "unmet_demand_crates"].iloc[0])
    colors = [POLICY_COLOR.get(policy, DATA) for policy in ordered["policy"]]
    deltas = ordered["unmet_demand_crates"] - baseline
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=ordered["policy_label"],
            y=ordered["unmet_demand_crates"],
            marker_color=colors,
            text=[f"{delta:+.0f} vs do nothing" if policy != "do_nothing" else "baseline" for policy, delta in zip(ordered["policy"], deltas)],
            textposition="outside",
            textfont=dict(color=INK, size=12),
            hovertemplate="%{x}<br>%{y:.1f} crates unmet<extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_yaxes(title="Simulated unmet demand (crates)", gridcolor=GRID, rangemode="tozero")
    fig.update_xaxes(title="Policy", gridcolor=GRID)
    return _base(fig, "Unmet demand compared with do nothing", height=420)


def contribution_bars(contributions: dict[str, float]) -> go.Figure:
    names = list(contributions)
    values = [float(contributions[name]) for name in names]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker_color=[DATA, CHAMPAGNE, "#9BC7BB", RISK],
            hovertemplate="%{y}<br>%{x:.3f} score points<extra></extra>",
        )
    )
    fig.update_xaxes(title="Contribution to the risk score", gridcolor=GRID, rangemode="tozero")
    fig.update_yaxes(title="", gridcolor=GRID, autorange="reversed")
    return _base(fig, "What drove this score", height=280)


def network_figure(
    net: SupplyNetwork,
    propagation: pd.DataFrame,
    risk: pd.DataFrame,
    disrupted_edge: str | None,
) -> go.Figure:
    columns = {"supplier": 0.0, "warehouse": 1.15, "hub": 2.3, "retailer": 3.45}
    grouped: dict[str, list] = {key: [] for key in columns}
    for node in net.nodes.values():
        grouped[node.node_type].append(node)
    positions: dict[str, tuple[float, float]] = {}
    for node_type, members in grouped.items():
        members = sorted(members, key=lambda item: DISPLAY_ORDER.index(item.node_id) if item.node_id in DISPLAY_ORDER else 99)
        count = len(members)
        for index, node in enumerate(members):
            y = 0.5 if count == 1 else 1.0 - (index / (count - 1))
            positions[node.node_id] = (columns[node_type], y)

    shortage = set(propagation.loc[propagation["predicted_shortage"], "node_id"]) if not propagation.empty else set()
    direct = set(propagation.loc[propagation["relationship"] == "directly affected", "node_id"]) if not propagation.empty else set()
    exposed = set(propagation.loc[propagation["relationship"] == "downstream exposed", "node_id"]) if not propagation.empty else set()
    score: dict[str, float] = {}
    if not risk.empty:
        for node_id, value in risk.groupby("node_id")["risk_score"].max().items():
            score[str(node_id)] = float(value)

    fig = go.Figure()
    role_style = {
        "primary": dict(color="#7F9E93", dash="solid", width=1.6),
        "alternate": dict(color=DATA, dash="dash", width=1.4),
        "lateral": dict(color=CHAMPAGNE, dash="dot", width=1.3),
    }
    for role, style in role_style.items():
        xs: list[float | None] = []
        ys: list[float | None] = []
        for edge in net.edges.values():
            if edge.role != role or (disrupted_edge and edge.edge_id == disrupted_edge):
                continue
            x0, y0 = positions[edge.source]
            x1, y1 = positions[edge.target]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=role.capitalize() + " lane", line=style, hoverinfo="skip"))

    if disrupted_edge and disrupted_edge in net.edges:
        edge = net.edges[disrupted_edge]
        x0, y0 = positions[edge.source]
        x1, y1 = positions[edge.target]
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                name="Disrupted lane",
                line=dict(color=RISK, width=4),
                hoverinfo="skip",
            )
        )

    hover_x, hover_y, hover_text = [], [], []
    for edge in net.edges.values():
        x0, y0 = positions[edge.source]
        x1, y1 = positions[edge.target]
        flag = "Disrupted on this run." if edge.edge_id == disrupted_edge else edge.role.capitalize() + " lane."
        hover_x.append((x0 + x1) / 2)
        hover_y.append((y0 + y1) / 2)
        hover_text.append(
            f"{edge.edge_id}: {edge.source} → {edge.target}<br>{flag}<br>"
            f"Lead {edge.lead_time_days} days · capacity {edge.capacity_per_day:.0f} crates/day · "
            f"cost {edge.cost_per_unit:.2f} units/crate"
        )
    fig.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,
            mode="markers",
            name="Lane detail",
            marker=dict(size=8, color="rgba(0,0,0,0)"),
            hovertext=hover_text,
            hoverinfo="text",
            showlegend=False,
        )
    )

    for node in net.nodes.values():
        x, y = positions[node.node_id]
        if node.node_id in shortage:
            color, status = RISK, "Predicted shortage"
        elif node.node_id in direct:
            color, status = "#E0B07A", "Directly affected"
        elif node.node_id in exposed:
            color, status = CHAMPAGNE, "Downstream exposed"
        else:
            color, status = TYPE_COLOR[node.node_type], node.node_type.capitalize()
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                hovertext=[
                    f"{node.node_id} · {node.name}<br>{node.place}<br>"
                    f"Type: {node.node_type}<br>Status: {status}<br>"
                    f"Highest risk score this morning: {score.get(node.node_id, 0):.2f}"
                ],
                hoverinfo="text",
                marker=dict(size=18, color=color, symbol=TYPE_SYMBOL[node.node_type], line=dict(width=1.2, color=INK)),
                showlegend=False,
            )
        )
        fig.add_annotation(
            x=x,
            y=y,
            text=node.node_id,
            showarrow=False,
            yshift=22,
            font=dict(size=11, color=SAGE, family="Segoe UI, sans-serif"),
        )

    for node_type, x in columns.items():
        fig.add_annotation(
            x=x,
            y=1.22,
            text=node_type.capitalize() + "s",
            showarrow=False,
            font=dict(size=13, color=CHAMPAGNE, family="Palatino, Georgia, serif"),
        )
    fig.update_xaxes(visible=False, range=[-0.42, 4.05])
    fig.update_yaxes(visible=False, range=[-0.18, 1.38])
    fig.update_layout(height=680)
    return _base(fig, "Illustrative supply network — four tiers, left to right")
