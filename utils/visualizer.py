from __future__ import annotations

import plotly.graph_objects as go


TYPE_STYLES = {
    "safe_zone": {"color": "#a6da95", "symbol": "circle", "size": 18},
    "hospital": {"color": "#8aadf4", "symbol": "circle", "size": 14},
    "shelter": {"color": "#c6a0f6", "symbol": "circle", "size": 14},
    "bridge": {"color": "#f5a97f", "symbol": "diamond", "size": 14},
    "intersection": {"color": "#5b6078", "symbol": "circle", "size": 10},
}

def build_city_map(
    city_graph_data,
    highlight_paths=None,
    step_annotations=None,
    blocked_edges=None,
    agent_positions=None,
    node_people=None,
    safe_zone_occupancy=None,
    isolated_nodes=None,
    show_labels=True,
) -> go.Figure:
    nodes = {n["id"]: n for n in city_graph_data.get("nodes", [])}
    positions = {nid: (float(n.get("x", 0.0)), float(n.get("y", 0.0))) for nid, n in nodes.items()}
    edge_meta = {}
    for e in city_graph_data.get("edges", []):
        edge_meta[tuple(sorted((e["source"], e["target"])))] = e
    blocked = {tuple(sorted((u, v))) for u, v in (blocked_edges or [])}

    fig = go.Figure()
    for e in city_graph_data.get("edges", []):
        u, v = e["source"], e["target"]
        x0, y0 = positions[u]
        x1, y1 = positions[v]
        key = tuple(sorted((u, v)))
        is_air = bool(e.get("air_only", False) or e.get("road_type") == "air")
        color = "#91d7e3" if is_air else "rgba(91,96,120,0.75)"
        dash = "dash" if is_air else "solid"
        if key in blocked:
            color = "#ed8796"
            dash = "dash"

        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color=color, width=1.5 if is_air else 1, dash=dash),
                hoverinfo="text",
                hovertext=f"{e.get('road_name','Road')}<br>{u} ↔ {v}<br>{float(e.get('distance_km',0)):.2f} km • {float(e.get('base_travel_time_min',0)):.0f} min",
                showlegend=False,
            )
        )

    if highlight_paths:
        for p in highlight_paths:
            path = p.get("path", [])
            color = p.get("color", "#a6da95")
            width = int(p.get("width", 3))
            label = p.get("label", "Path")
            dash = p.get("dash", "solid")
            show_steps = bool(p.get("show_steps", False))
            opacity = float(p.get("opacity", 1.0))
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                if u not in positions or v not in positions:
                    continue
                x0, y0 = positions[u]
                x1, y1 = positions[v]
                fig.add_trace(
                    go.Scatter(
                        x=[x0, x1],
                        y=[y0, y1],
                        mode="lines",
                        line=dict(color=color, width=width, dash=dash),
                        opacity=opacity,
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
                fig.add_annotation(
                    x=x1,
                    y=y1,
                    ax=x0,
                    ay=y0,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    text="",
                    showarrow=True,
                    arrowhead=3,
                    arrowsize=1,
                    arrowwidth=1.2,
                    arrowcolor=color,
                )
                if show_steps:
                    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                    fig.add_annotation(
                        x=mx,
                        y=my,
                        text=str(i + 1),
                        showarrow=False,
                        font=dict(size=10, color="#cad3f5"),
                        bgcolor=color,
                        opacity=0.9,
                    )
            fig.add_shape(type="line", x0=0, y0=0, x1=0.02, y1=0, xref="paper", yref="paper")
            fig.add_annotation(
                x=0.02,
                y=0.03 + 0.03 * (highlight_paths.index(p)),
                xref="paper",
                yref="paper",
                text=f"<span style='color:{color};'>━━</span> {label}",
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
            )

    xs, ys, sizes, colors, symbols, hovers, texts = [], [], [], [], [], [], []
    for nid, n in nodes.items():
        x, y = positions[nid]
        nt = n.get("type", "intersection")
        style = TYPE_STYLES.get(nt, TYPE_STYLES["intersection"])
        base_size = float(style["size"])
        if node_people is not None:
            p = int(node_people.get(nid, int(n.get("people_stranded", 0))))
            base_size = max(base_size, 8 + min(26, (p / 25.0)))
        xs.append(x)
        ys.append(y)
        sizes.append(base_size)
        colors.append(style["color"])
        symbols.append(style["symbol"])
        label = nid
        hovers.append(f"<b>{label}</b><br>Node: {nid}<br>Type: {nt}<br>People stranded: {int(n.get('people_stranded', 0))}")
        texts.append(label if show_labels else "")

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text" if show_labels else "markers",
            text=texts,
            textposition="top center",
            marker=dict(size=sizes, color=colors, symbol=symbols, opacity=0.95),
            hoverinfo="text",
            hovertext=hovers,
            showlegend=False,
        )
    )

    for nid, n in nodes.items():
        if not n.get("helipad"):
            continue
        x, y = positions[nid]
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                marker=dict(symbol="square", size=7, color="#cad3f5", line=dict(color="#181926", width=1)),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if agent_positions:
        ax, ay, acol, ahover, asymbols, alabels = [], [], [], [], [], []
        for unit_id, info in agent_positions.items():
            node_id = info.get("node_id")
            color = info.get("color", "#8aadf4")
            mode = info.get("mode", "ground")
            if node_id not in positions:
                continue
            x, y = positions[node_id]
            ax.append(x)
            ay.append(y)
            acol.append(color)
            asymbols.append("diamond" if mode == "air" else "star")
            alabels.append("AIR" if mode == "air" else "")
            ahover.append(f"{unit_id}<br>At: {node_id}")

        if ax:
            fig.add_trace(
                go.Scatter(
                    x=ax,
                    y=ay,
                    mode="markers+text",
                    text=alabels,
                    textposition="middle right",
                    marker=dict(symbol=asymbols, size=16, color=acol, line=dict(color="#cad3f5", width=1)),
                    hoverinfo="text",
                    hovertext=ahover,
                    showlegend=False,
                )
            )

    if step_annotations:
        for item in step_annotations:
            node_id = item["node_id"]
            if node_id not in positions:
                continue
            x, y = positions[node_id]
            visited = bool(item.get("visited"))
            is_current = bool(item.get("current"))
            fill = "#a6da95" if visited else "#363a4f"
            if is_current:
                fill = "#8aadf4"
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="markers+text",
                    text=[str(item.get("step_number", 0))],
                    textposition="middle center",
                    marker=dict(
                        color=fill,
                        size=20 if is_current else 16,
                        symbol="circle",
                        line=dict(color="#cad3f5" if is_current else "#5b6078", width=3 if is_current else 1),
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    if isolated_nodes:
        for nid in isolated_nodes:
            if nid not in positions:
                continue
            x, y = positions[nid]
            fig.add_shape(
                type="circle",
                xref="x",
                yref="y",
                x0=x - 0.25,
                y0=y - 0.25,
                x1=x + 0.25,
                y1=y + 0.25,
                line=dict(color="#eed49f", width=2, dash="dot"),
            )

    fig.add_annotation(
        x=0.99,
        y=0.02,
        xref="paper",
        yref="paper",
        text="Road: <span style='color:#5b6078;'>━━</span><br>Air Corridor: <span style='color:#91d7e3;'>- - -</span><br>Blocked Road: <span style='color:#ed8796;'>- - -</span>",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
    )

    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, gridcolor="#494d64", zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, gridcolor="#494d64", zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        paper_bgcolor="#24273a",
        plot_bgcolor="#24273a",
        font=dict(color="#cad3f5"),
        height=560,
    )
    return fig

