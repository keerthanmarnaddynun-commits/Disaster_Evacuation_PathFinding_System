"""Disaster simulation: block roads, spread events."""

from __future__ import annotations

import streamlit as st

from core import data_loader, disaster_manager
from utils import visualizer
from utils import app_state


def render() -> None:
    st.header("Disaster Simulation Panel")
    G = app_state.get_city_graph()
    events = data_loader.read_disaster_events()
    blocked = disaster_manager.collect_blocked_edges(events)

    st.subheader("Map — click data point not supported; pick nodes/edges below")
    fig = visualizer.render_city_graph(G, blocked_edges=blocked, title="Current blocks (red)")
    st.plotly_chart(fig, use_container_width=True)

    edge_list = sorted({tuple(sorted((u, v))) for u, v in G.edges()})
    edge_labels = [f"{a} — {b} ({G.edges[a, b].get('road_name', '')})" for a, b in edge_list]

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Block / restore road")
        pick = st.selectbox("Edge", list(range(len(edge_list))), format_func=lambda i: edge_labels[i])
        u, v = edge_list[pick]
        if st.button("Block selected edge"):
            disaster_manager.block_road(G, u, v)
            app_state.refresh_base_graph()
            st.rerun()
        if st.button("Restore selected edge"):
            disaster_manager.unblock_road(G, u, v)
            app_state.refresh_base_graph()
            st.rerun()

    with c2:
        st.subheader("New disaster event")
        dtype = st.selectbox("Type", ["flood", "earthquake", "fire", "congestion"])
        sev = st.selectbox("Severity", ["low", "medium", "high", "critical"])
        epicenter = st.selectbox("Epicenter node", sorted(G.nodes()))
        radius = st.slider("Spread radius (map units)", 1.0, 25.0, 10.0)
        if st.button("Spread disaster"):
            disaster_manager.spread_disaster(G, epicenter, radius, dtype, severity=sev)
            app_state.refresh_base_graph()
            st.rerun()

    st.subheader("Blocked roads (restore)")
    rows = []
    for pair in sorted(blocked):
        rows.append({"u": pair[0], "v": pair[1]})
    st.dataframe(rows, use_container_width=True)

    for pair in sorted(blocked):
        b1, b2 = st.columns([3, 1])
        with b1:
            st.text(f"{pair[0]} ↔ {pair[1]}")
        with b2:
            if st.button("Restore", key=f"rest_{pair[0]}_{pair[1]}"):
                disaster_manager.unblock_road(G, pair[0], pair[1])
                app_state.refresh_base_graph()
                st.rerun()

    st.subheader("Before / after (reload graph)")
    st.caption("After blocking, edges removed from working graph; JSON drives persistence.")


if __name__ == "__main__":
    render()
