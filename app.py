"""
Veridian City — Disaster Evacuation Route Optimization & Rescue System
Entry point: streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

# Ensure project root is importable
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pages import analytics, dashboard, disaster_control, rescue_ops, route_planner

st.set_page_config(
    page_title="Veridian City — Disaster & Rescue",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("Veridian City")
st.sidebar.caption("Disaster evacuation & rescue coordination")

with st.sidebar:
    selected = option_menu(
        "Navigate",
        [
            "City Overview",
            "Evacuation Route Planner",
            "Disaster Simulation",
            "Rescue Coordination",
            "Algorithm Analytics",
        ],
        menu_icon="house",
        default_index=0,
    )

if selected == "City Overview":
    dashboard.render()
elif selected == "Evacuation Route Planner":
    route_planner.render()
elif selected == "Disaster Simulation":
    disaster_control.render()
elif selected == "Rescue Coordination":
    rescue_ops.render()
elif selected == "Algorithm Analytics":
    analytics.render()
