"""Plotly/Matplotlib city graph visualization."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from core import data_loader, graph_engine
from core.disaster_manager import collect_blocked_edges, compute_risk_score


def _node_color(
    nid: str,
    data: dict[str, Any],
    *,
    disaster_affected: set[str],
    risk_mode: bool,
    active_events: list[dict],
) -> str:
    nt = data.get("node_type", "intersection")
    if risk_mode:
        r = compute_risk_score(nid, active_events)
        if r < 0.25:
            return "#22c55e"
        if r < 0.5:
            return "#eab308"
        if r < 0.75:
            return "#f97316"
        return "#ef4444"
    if nt == "safe_zone":
        return "#22c55e"
    if nid in disaster_affected:
        return "#ef4444"
    if nt == "hospital":
        return "#f97316"
    if nt == "bridge":
        return "#8b5cf6"
    if nt == "shelter":
        return "#06b6d4"
    return "#3b82f6"


def render_city_graph(
    G: nx.Graph,
    highlighted_path: list[str] | None = None,
    blocked_edges: set[tuple[str, str]] | None = None,
    disaster_zones: list[str] | None = None,
    *,
    show_risk_heatmap: bool = False,
    title: str = "Veridian City",
) -> go.Figure:
    """
    Interactive Plotly graph. Edges: blocked red, congested yellow, path green, normal gray.
    """
    _ = disaster_zones
    events = data_loader.read_disaster_events()
    if blocked_edges is None:
        blocked_edges = collect_blocked_edges(events)

    disaster_affected: set[str] = set()
    for ev in events:
        if ev.get("active"):
            disaster_affected.update(ev.get("affected_nodes", []))

    path_edges: set[tuple[str, str]] = set()
    if highlighted_path and len(highlighted_path) > 1:
        for i in range(len(highlighted_path) - 1):
            a, b = highlighted_path[i], highlighted_path[i + 1]
            path_edges.add((a, b) if a <= b else (b, a))

    traces: list[Any] = []
    for u, v, ed in G.edges(data=True):
        x0, y0 = float(G.nodes[u]["x"]), float(G.nodes[u]["y"])
        x1, y1 = float(G.nodes[v]["x"]), float(G.nodes[v]["y"])
        key = (u, v) if u <= v else (v, u)
        is_blocked = key in blocked_edges
        is_path = key in path_edges
        w = graph_engine.get_edge_weight(G, u, v, "fastest", active_events=events)
        road = ed.get("road_name", "")
        dist = ed.get("distance_km", 0)
        if is_path:
            color = "#22c55e"
            width = 5
        elif is_blocked:
            color = "#ef4444"
            width = 3
        elif float(ed.get("congestion_factor", 1)) > 1.12:
            color = "#eab308"
            width = 2
        else:
            color = "#94a3b8"
            width = 2
        traces.append(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color=color, width=width),
                hovertext=f"{road}<br>{u}↔{v}<br>{dist:.2f} km, est {w:.2f} min",
                hoverinfo="text",
                showlegend=False,
            )
        )

    colors = [
        _node_color(
            n,
            G.nodes[n],
            disaster_affected=disaster_affected,
            risk_mode=show_risk_heatmap,
            active_events=events,
        )
        for n in G.nodes()
    ]
    node_x = [float(G.nodes[n]["x"]) for n in G.nodes()]
    node_y = [float(G.nodes[n]["y"]) for n in G.nodes()]
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=[str(n) for n in G.nodes()],
        textposition="top center",
        marker=dict(size=14, color=colors, line=dict(width=1, color="#1e293b")),
        hovertext=[f"{n}<br>{G.nodes[n].get('name','')}<br>{G.nodes[n].get('node_type','')}" for n in G.nodes()],
        hoverinfo="text",
        name="nodes",
    )

    fig = go.Figure(data=traces + [node_trace], layout_title_text=title)
    fig.update_layout(
        showlegend=False,
        hovermode="closest",
        margin=dict(b=10, l=10, r=10, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        plot_bgcolor="#0f172a",
        paper_bgcolor="#020617",
        font=dict(color="#e2e8f0"),
        title=dict(font=dict(size=16)),
    )
    return fig


def render_comparison_chart(results: list[dict[str, Any]]) -> go.Figure:
    """Bar chart: algorithm vs cost and estimated time."""
    names = [r.get("algorithm", "?") for r in results]
    costs = [float(r.get("weighted_cost", r.get("cost", 0)) or 0) for r in results]
    times = [float(r.get("estimated_time", 0) or 0) for r in results]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Weighted cost / hops", x=names, y=costs, marker_color="#38bdf8"))
    fig.add_trace(go.Bar(name="Est. time (min)", x=names, y=times, marker_color="#a78bfa"))
    fig.update_layout(
        barmode="group",
        paper_bgcolor="#020617",
        plot_bgcolor="#0f172a",
        font=dict(color="#e2e8f0"),
        xaxis=dict(title="Algorithm"),
        yaxis=dict(title="Value"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
