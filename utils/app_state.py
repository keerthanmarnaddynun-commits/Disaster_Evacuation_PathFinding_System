"""Streamlit session helpers for graph caching."""

from __future__ import annotations

import streamlit as st

from core import data_loader, disaster_manager, graph_engine


def get_city_graph():
    """Full topology from disk with active disaster blocks applied (copy)."""
    if "_base_nx" not in st.session_state:
        st.session_state._base_nx = graph_engine.load_graph()
    events = data_loader.read_disaster_events()
    return disaster_manager.apply_blocked_to_graph(st.session_state._base_nx, events)


def refresh_base_graph() -> None:
    """Reload city_graph.json into session (e.g. after external edits)."""
    st.session_state._base_nx = graph_engine.load_graph()


def blocked_edge_set():
    return disaster_manager.collect_blocked_edges(data_loader.read_disaster_events())
