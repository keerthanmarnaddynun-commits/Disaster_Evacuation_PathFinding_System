"""City Overview dashboard."""

from __future__ import annotations

import streamlit as st

from core import data_loader, disaster_manager
from utils import visualizer
from utils import app_state


def render() -> None:
    st.header("Veridian City — Overview")
    G = app_state.get_city_graph()
    events = data_loader.read_disaster_events()
    safe = data_loader.read_safe_zones()

    active = [e for e in events if e.get("active")]
    z_at_risk: set[str] = set()
    for e in active:
        z_at_risk.update(disaster_manager.get_affected_zones(G, e))
    at_risk = len(z_at_risk)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total nodes", G.number_of_nodes())
    c2.metric("Active disasters", len(active))
    c3.metric("Zones touched", at_risk)
    c4.metric("Safe zones", len(safe))

    st.subheader("Interactive city map")
    heat = st.checkbox("Risk heatmap overlay", value=True)
    fig = visualizer.render_city_graph(G, show_risk_heatmap=heat, title="City graph (blocked = red)")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Active disaster events")
    st.dataframe(active, use_container_width=True)

    st.subheader("Quick actions")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Simulate Earthquake", key="sim_eq"):
            disaster_manager.spread_disaster(G, "N015", 14.0, "earthquake", severity="high")
            app_state.refresh_base_graph()
            st.rerun()
    with b2:
        if st.button("Simulate Flood", key="sim_fl"):
            disaster_manager.spread_disaster(G, "N004", 12.0, "flood", severity="high")
            app_state.refresh_base_graph()
            st.rerun()
    with b3:
        if st.button("Clear All Disasters", key="clr"):
            evs = data_loader.read_disaster_events()
            for e in evs:
                e["active"] = False
            data_loader.write_disaster_events(evs)
            app_state.refresh_base_graph()
            st.rerun()


if __name__ == "__main__":
    render()
