from __future__ import annotations

import streamlit as st
from streamlit_option_menu import option_menu

from core.data_loader import (
    load_city_graph,
    load_disaster_events,
    load_rescue_units,
    load_resources,
    load_safe_zones,
    save_city_graph,
    save_disaster_events,
    save_rescue_units,
    save_resources,
    save_safe_zones,
)
from pages import dashboard, disaster_control, rescue_ops, resource_hub

CITY_OPTIONS = ["Map 1", "Map 2", "Map 3"]


def reset_all_state():
    """
    Called once per app session on first load.
    Resets all runtime data back to zero defaults.
    Does NOT touch the city graph structure (nodes, edges, coordinates).
    Resets only mutable runtime state.
    """
    for map_name in CITY_OPTIONS:
        city = load_city_graph(map_name)
        for node in city.get("nodes", []):
            node["people_stranded"] = 0
            node["rescued"] = False
            node["injury_level"] = "none"
            node["rescue_cost"] = 0
            node["survival_chance"] = 1.0
            node["risk_score"] = 0.0
        save_city_graph(city, map_name)

        zones = load_safe_zones(map_name)
        for zone in zones:
            zone["current_occupancy"] = 0
            zone["resources"] = {
                "food_packets": 0,
                "water_liters": 0,
                "medical_kits": 0,
                "blankets": 0,
            }
            zone["victims"] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "recovered": 0, "total": 0}
        save_safe_zones(zones, map_name)

        save_disaster_events([], map_name)

        units = load_rescue_units(map_name)
        for unit in units:
            default_kits = unit.get("default_medical_kits", unit.get("medical_kits", 0))
            unit["default_medical_kits"] = default_kits
            unit["status"] = "available"
            unit["current_node"] = unit.get("base_node")
            unit["fuel_remaining"] = unit.get("fuel_capacity", 0)
            unit["medical_kits"] = default_kits
            unit["total_rescued"] = 0
            unit["rescued_nodes"] = []
        save_rescue_units(units, map_name)

    with open("data/active_missions.json", "w", encoding="utf-8") as f:
        f.write('{"missions": []}\n')

    rescue_header = (
        "log_id,timestamp,city,team_id,team_name,team_type,from_node,"
        "to_node,algorithm_used,path_length,nodes_explored,time_ms,"
        "people_rescued,fuel_used,status\n"
    )
    with open("data/rescue_log.csv", "w", encoding="utf-8") as f:
        f.write(rescue_header)

    resources = load_resources()
    for item in resources.get("inventory", []):
        item["distributed"] = 0
        item["in_transit"] = 0
    resources["safe_zone_allocations"] = []
    resources["distribution_log"] = []
    save_resources(resources)

    st.session_state["auto_advance"] = {}
    st.session_state["last_advance_time"] = {}
    st.session_state["selected_target"] = None
    st.session_state["selected_team"] = None
    st.session_state["active_map"] = "Map 1"
    st.session_state["active_city"] = "Map 1"

st.set_page_config(
    page_title="City Disaster Management System",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
#MainMenu, footer, header {visibility: hidden;}
body, [data-testid="stAppViewContainer"] { background: #24273a; color: #cad3f5; }
[data-testid="stSidebar"] { width: 260px !important; min-width: 260px !important; background: #1e2030; }
h1, h2, h3, h4, h5, h6 { color: #cad3f5; }
p, span, label, div { color: #b8c0e0; }
a { color: #8aadf4 !important; }
.card { background: #363a4f; border: 1px solid #494d64; border-radius: 12px; padding: 16px; }
.badge-green { background:#a6da95; color:#181926; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-red { background:#ed8796; color:#181926; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-yellow { background:#eed49f; color:#181926; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-blue { background:#8aadf4; color:#181926; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.badge-gray { background:#5b6078; color:#cad3f5; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.85rem; }
.stMetric label, [data-testid="stMetricLabel"] { color: #b8c0e0 !important; }
.stMetric [data-testid="stMetricValue"] { color: #cad3f5 !important; }
[data-testid="stSidebar"] .nav-link:hover { background: #494d64 !important; }
[data-testid="stSidebar"] .nav-link-selected { background-color: #8aadf4 !important; color: #181926 !important; border-radius: 8px; }
*::-webkit-scrollbar-thumb { background: #5b6078; border-radius: 8px; }
*::-webkit-scrollbar-track { background: #1e2030; }
.stDataFrame, .stTable { background: #363a4f !important; color: #cad3f5 !important; }
.stSelectbox > div > div, .stNumberInput > div > div, .stTextInput > div > div { background: #494d64 !important; color: #cad3f5 !important; }
.stButton > button { background:#8aadf4; color:#181926; border:none; border-radius:8px; }
.stButton > button:hover { background:#7dc4e4; color:#181926; border:none; }
.stTabs [data-baseweb="tab"] { color: #b8c0e0; }
.stTabs [aria-selected="true"] { color: #cad3f5; border-bottom: 2px solid #8aadf4; }
.stDisabled, .muted { color: #8087a2 !important; }
</style>
    """,
    unsafe_allow_html=True,
)

if "initialized" not in st.session_state:
    reset_all_state()
    st.session_state["initialized"] = True
if "active_map" not in st.session_state:
    st.session_state["active_map"] = "Map 1"
if "active_city" not in st.session_state:
    st.session_state["active_city"] = st.session_state["active_map"]

with st.sidebar:
    city = st.selectbox(
        "Active Map",
        CITY_OPTIONS,
        index=CITY_OPTIONS.index(st.session_state["active_map"]),
    )
    if city != st.session_state["active_map"]:
        st.session_state["active_map"] = city
        st.session_state["active_city"] = city
        st.rerun()

    st.markdown(
        """
        <div style="font-size:1.35rem;font-weight:800;color:#cad3f5;">Disaster Response Console</div>
        <div style="color:#b8c0e0;margin-top:4px;">Admin-controlled rescue operations</div>
        <hr style="border:0;border-top:1px solid #494d64;margin:12px 0;" />
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
            "container": {"padding": "0", "background-color": "#1e2030"},
            "nav-link": {"font-size": "0.95rem", "text-align": "left", "margin": "2px 0", "--hover-color": "#494d64"},
            "nav-link-selected": {"background-color": "#8aadf4", "color": "#181926", "border-radius": "8px"},
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

