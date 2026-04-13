from __future__ import annotations

from datetime import datetime

import streamlit as st
from streamlit_option_menu import option_menu

from pages import dashboard, disaster_control, rescue_ops, resource_hub

CITY_OPTIONS = ["Veridian City", "Harborfield", "Maplecrest"]

st.set_page_config(
    page_title="City Disaster Management System",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
#MainMenu, footer, header {visibility: hidden;}
[data-testid="stSidebar"] { width: 260px !important; min-width: 260px !important; background: #13152a; }
.card { background: #1a1d2e; border: 1px solid #2d3154; border-radius: 12px; padding: 16px; }
.badge-green { background:#2ecc71; color:#0f1117; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-red { background:#e74c3c; color:#ffffff; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-yellow { background:#f39c12; color:#0f1117; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-blue { background:#4f8ef7; color:#ffffff; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-gray { background:#2d3154; color:#ffffff; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
</style>
    """,
    unsafe_allow_html=True,
)

if "active_city" not in st.session_state:
    st.session_state["active_city"] = "Veridian City"

with st.sidebar:
    city = st.selectbox("Active City", CITY_OPTIONS, index=CITY_OPTIONS.index(st.session_state["active_city"]))
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

    st.markdown(
        f"""
        <hr style="border:0;border-top:1px solid #2d3154;margin:12px 0;" />
        <div style="color:#a0a8c0;font-size:0.82rem;">
          DAA Project<br/>
          {datetime.now().strftime("%b %d, %Y")}
        </div>
        """,
        unsafe_allow_html=True,
    )

if selected == "City Overview":
    dashboard.render()
elif selected == "Disaster Control":
    disaster_control.render()
elif selected == "Rescue Operations":
    rescue_ops.render()
else:
    resource_hub.render()

