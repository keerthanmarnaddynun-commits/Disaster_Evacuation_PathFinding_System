from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.data_loader import load_city_graph, load_disaster_events, load_evacuation_zones, load_safe_zones
from core.graph_engine import load_graph
from core.disaster_manager import compute_risk_score, get_all_blocked_edges
from core.mission_manager import MissionManager
from utils.visualizer import build_city_map

MAP_OPTIONS = ["Map 1", "Map 2", "Map 3"]


def _risk_badge(level: str) -> str:
    level = (level or "").lower()
    if level == "critical":
        return '<span class="badge-red">critical</span>'
    if level == "high":
        return '<span class="badge-yellow">high</span>'
    if level == "medium":
        return '<span class="badge-blue">medium</span>'
    return '<span class="badge-green">low</span>'


def render():
    active_city = st.session_state.get("active_map", "Map 1")
    city = load_city_graph(active_city)
    events = load_disaster_events(active_city)
    zones = load_evacuation_zones(active_city)
    safe_zones = load_safe_zones(active_city)

    G = load_graph(city)
    blocked = get_all_blocked_edges(events)

    # Inject risk_score into nodes for hover display
    for n in city["nodes"]:
        n["risk_score"] = compute_risk_score(n["id"], events, G)

    active_events = [e for e in events if e.get("active", False)]
    safe_available = sum(1 for sz in safe_zones if int(sz.get("current_occupancy", 0)) < int(sz.get("capacity", 1)))

    total_nodes = len(city.get("nodes", []))
    roads_blocked = len(blocked)
    zones_at_risk = sum(1 for z in zones if (z.get("risk_level") in {"critical", "high"}))

    st.subheader("City Selector")
    cols = st.columns(3)
    for i, opt in enumerate(MAP_OPTIONS):
        with cols[i]:
            if st.button(opt, width="stretch", type="primary" if opt == active_city else "secondary"):
                st.session_state["active_map"] = opt
                st.session_state["active_city"] = opt
                st.rerun()

    st.markdown(
        f"""
        <div style="margin-bottom: 0.75rem;">
          <div style="font-size:2rem;font-weight:700;color:#cad3f5;">{active_city} - Disaster Command Center</div>
        <div style="color:#b8c0e0;">{datetime.now().strftime("%A, %b %d %Y • %H:%M:%S")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Nodes", total_nodes)
    c2.metric("Active Disasters", len(active_events))
    c3.metric("Roads Blocked", roads_blocked)
    c4.metric("Zones at Risk", zones_at_risk)
    c5.metric("Safe Zones Available", safe_available)

    left, right = st.columns([0.7, 0.3], gap="large")

    with left:
        fig = build_city_map(city, blocked_edges=blocked, show_labels=False)
        st.plotly_chart(fig, width="stretch")

    with right:
        st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Active Disaster Events</div>', unsafe_allow_html=True)
        if not active_events:
            st.markdown('<div class="card" style="color:#b8c0e0;">No active disasters</div>', unsafe_allow_html=True)
        for e in active_events:
            sev = str(e.get("severity", "low")).lower()
            sev_badge = (
                '<span class="badge-red">critical</span>'
                if sev == "critical"
                else '<span class="badge-yellow">high</span>'
                if sev == "high"
                else '<span class="badge-blue">medium</span>'
                if sev == "medium"
                else '<span class="badge-green">low</span>'
            )
            st.markdown(
                f"""
                <div class="card">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-weight:700;color:#cad3f5;">{str(e.get("type")).title()}</div>
                    <div>{sev_badge}</div>
                  </div>
                  <div style="margin-top:0.5rem;color:#d8dee9;">
                    Affected nodes: <b style="color:#cad3f5;">{len(e.get("affected_nodes", []))}</b><br/>
                    Blocked roads: <b style="color:#cad3f5;">{len(e.get("blocked_edges", []))}</b><br/>
                    Timestamp: {e.get("timestamp","")}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div style="margin-top:0.75rem;font-size:1.1rem;font-weight:600;color:#91d7e3;">Zone Risk Table</div>', unsafe_allow_html=True)
    mm = MissionManager()
    mission_rows = [m for m in mm.load() if m.get("city") == active_city and m.get("status") != "complete"]
    if mission_rows:
        st.markdown("### Mission Overview")
        cols = st.columns(3)
        for i, m in enumerate(mission_rows):
            with cols[i % 3]:
                st.markdown(f"**{m['team_name']}**  \n{m['status']}  \nTarget: {m['target_node']}  \nStep {m['current_step']}/{max(1, len(m['path'])-1)}")
                if st.button("View Mission", key=f"vm_{m['mission_id']}"):
                    st.session_state["nav_to"] = "Rescue Operations"
        palette = ["#a6da95", "#91d7e3", "#8aadf4", "#c6a0f6", "#ed8796"]
        highlight = []
        for i, m in enumerate(mission_rows):
            highlight.append({"path": m["path"], "color": palette[i % len(palette)], "width": 3, "label": m["mission_id"], "dash": "solid", "show_steps": False})
        st.plotly_chart(build_city_map(city, highlight_paths=highlight, show_labels=False), width="stretch")

    # Blocked roads per zone (count edges where either endpoint is in zone)
    zone_nodes = {z["zone_id"]: set(z.get("nodes", [])) for z in zones}
    zone_blocked = {}
    for zid, nset in zone_nodes.items():
        cnt = 0
        for u, v in blocked:
            if u in nset or v in nset:
                cnt += 1
        zone_blocked[zid] = cnt

    rows = []
    for z in zones:
        rows.append(
            {
                "Zone": z.get("zone_id"),
                "Risk Level": z.get("risk_level", "low"),
                "Population": z.get("population", 0),
                "Nodes": len(z.get("nodes", [])),
                "Blocked Roads": zone_blocked.get(z.get("zone_id"), 0),
            }
        )

    zone_df = pd.DataFrame(rows)
    st.dataframe(zone_df, width="stretch")

    stranded = pd.DataFrame(city["nodes"])[["zone", "people_stranded"]].groupby("zone", as_index=False)["people_stranded"].sum()
    stranded = stranded.rename(columns={"zone": "Zone", "people_stranded": "Total Stranded"})
    stranded["Critical Injury"] = 0
    stranded["High Injury"] = 0
    stranded["Available Teams"] = 0
    stranded["Status"] = stranded["Total Stranded"].apply(lambda x: "Needs Rescue" if x > 0 else "Stable")
    st.subheader("Stranded Population Summary")
    st.dataframe(stranded, width="stretch")

