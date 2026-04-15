from __future__ import annotations

from datetime import datetime

import streamlit as st
from streamlit_option_menu import option_menu

from core.data_loader import reset_resource_runtime_state
from pages import dashboard, disaster_control, rescue_ops, resource_hub

CITY_OPTIONS = ["Veridian City", "Harborfield", "Maplecrest"]
CITY_LABELS = {
    "Veridian City": "Map 1",
    "Harborfield": "Map 2",
    "Maplecrest": "Map 3",
}

st.set_page_config(
    page_title="City Disaster Management System",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
#MainMenu, footer, header {visibility: hidden;}
[data-testid="stAppViewContainer"] { background: #2e3440; }
[data-testid="stSidebar"] { width: 260px !important; min-width: 260px !important; background: #3b4252; }
.stButton > button { background:#5e81ac; color:#eceff4; border:1px solid #81a1c1; border-radius:8px; }
.stButton > button:hover { background:#81a1c1; color:#2e3440; border-color:#88c0d0; }
.card { background: #434c5e; border: 1px solid #4c566a; border-radius: 12px; padding: 16px; }
.badge-green { background:#8fbcbb; color:#2e3440; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-red { background:#bf616a; color:#ffffff; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-yellow { background:#ebcb8b; color:#2e3440; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-blue { background:#81a1c1; color:#ffffff; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-gray { background:#4c566a; color:#eceff4; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
</style>
    """,
    unsafe_allow_html=True,
)

if "active_city" not in st.session_state:
    st.session_state["active_city"] = "Veridian City"
if "session_bootstrap_done" not in st.session_state:
    reset_resource_runtime_state()
    st.session_state["session_bootstrap_done"] = True

with st.sidebar:
    city = st.selectbox(
        "Active Map",
        CITY_OPTIONS,
        index=CITY_OPTIONS.index(st.session_state["active_city"]),
        format_func=lambda c: CITY_LABELS.get(c, c),
    )
    if city != st.session_state["active_city"]:
        st.session_state["active_city"] = city
        st.rerun()

    st.markdown(
        """
        <div style="font-size:1.35rem;font-weight:800;color:#ffffff;">Disaster Response Console</div>
        <div style="color:#a0a8c0;margin-top:4px;">Admin-controlled rescue operations</div>
        <hr style="border:0;border-top:1px solid #2d3154;margin:12px 0;" />
        """,
        unsafe_allow_html=True,
    )

    selected = option_menu(
        None,
        ["City Overview", "Disaster Control", "Rescue Operations", "Resource Hub"],
        icons=[None, None, None, None, None],
        menu_icon=None,
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": "#13152a"},
            "nav-link": {"font-size": "0.95rem", "text-align": "left", "margin": "2px 0", "--hover-color": "#1e2140"},
            "nav-link-selected": {"background-color": "#4f8ef7", "color": "#ffffff", "border-radius": "8px"},
            "icon": {"display": "none"},
        },
    )


if selected == "City Overview":
    dashboard.render()
elif selected == "Disaster Control":
    disaster_control.render()
elif selected == "Rescue Operations":
    rescue_ops.render()
else:
    resource_hub.render()

