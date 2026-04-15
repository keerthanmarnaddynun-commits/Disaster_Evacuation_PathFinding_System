from __future__ import annotations

import random
from datetime import datetime

import pandas as pd
import streamlit as st

from core.data_loader import load_city_graph, load_disaster_events, load_rescue_units_df, save_city_graph, save_disaster_events
from core.mission_manager import MissionManager
from core.graph_engine import load_graph
from core.disaster_manager import spread_disaster, block_road, unblock_road, get_all_blocked_edges
from core.dynamic_obstacles import block_road_live
from utils.visualizer import build_city_map


def render():
    active_city = st.session_state.get("active_city", "Veridian City")
    st.markdown('<div style="font-size:2rem;font-weight:700;color:#ffffff;">Disaster Control Panel</div>', unsafe_allow_html=True)

    city = load_city_graph(active_city)
    events = load_disaster_events(active_city)
    G = load_graph(city)
    active_events = [e for e in events if e.get("active", True)]
    blocked = get_all_blocked_edges(events)

    node_id_to_name = {n["id"]: n["id"] for n in city.get("nodes", [])}
    st.markdown(f"Active city: {active_city}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Disasters", len(active_events))
    c2.metric("Blocked Roads", len(blocked))
    c3.metric("Affected Nodes", len({n for e in active_events for n in e.get('affected_nodes', [])}))
    c4.metric("Zones at Risk", len({n.get("zone", "") for n in city.get("nodes", []) if n["id"] in {x for e in active_events for x in e.get("affected_nodes", [])}}))
    st.plotly_chart(build_city_map(city, blocked_edges=blocked, show_labels=False), use_container_width=True)

    st.markdown("### Simulate New Disaster")
    form_left, form_right = st.columns([0.66, 0.34], gap="large")
    with form_left:
        dtype = st.selectbox("Disaster Type", ["Flood", "Earthquake", "Fire", "Landslide", "Congestion"], key="disaster_type")
    desc = {
        "Flood": "Blocks low-elevation roads and bridge nodes. Spreads along water paths.",
        "Earthquake": "Randomly blocks roads within radius. May isolate bridge nodes.",
        "Fire": "Blocks roads in spread pattern. Increases risk scores of nearby nodes.",
        "Landslide": "Blocks mountain or elevated roads. Can isolate nodes completely.",
        "Congestion": "Increases travel time on arterial and highway roads in the area.",
    }
    with form_left:
        st.caption(desc[dtype])
        epicenter = st.selectbox(
            "Epicenter Node",
            [n["id"] for n in city.get("nodes", [])],
            format_func=lambda x: f"{x} - {node_id_to_name[x]}",
            key="epicenter_node",
        )
    with form_right:
        severity = st.select_slider("Severity", ["Low", "Medium", "High", "Critical"], value="High", key="disaster_severity")
        radius = st.slider("Affected radius", 1, 5, 2, key="disaster_radius")
        preview = st.checkbox("Preview before triggering", key="preview_disaster")
    if preview:
        preview_event = spread_disaster(G, epicenter, radius, dtype.lower(), severity.lower())
        st.plotly_chart(build_city_map(city, blocked_edges=blocked, isolated_nodes=preview_event["affected_nodes"], show_labels=False), use_container_width=True)
        st.subheader("Disaster Impact Preview")
        ndf = pd.DataFrame(city.get("nodes", []))
        affected_df = ndf[ndf["id"].isin(preview_event.get("affected_nodes", []))][["id", "zone", "people_stranded"]]
        affected_df["Current Risk Score"] = affected_df["id"].apply(lambda x: 1)
        st.dataframe(affected_df.rename(columns={"id": "Node", "zone": "Zone", "people_stranded": "People Stranded"}), use_container_width=True)
        blocked_df = pd.DataFrame(preview_event.get("blocked_edges", []), columns=["From", "To"])
        blocked_df["Road Name"] = blocked_df["From"] + " - " + blocked_df["To"]
        blocked_df["Road Type"] = "local"
        st.dataframe(blocked_df[["Road Name", "From", "To", "Road Type"]], use_container_width=True)
        st.metric("Estimated people affected", int(affected_df["People Stranded"].sum()) if "People Stranded" in affected_df else 0)
        teams_df = load_rescue_units_df(active_city)
        if not teams_df.empty:
            affected_nodes = set(preview_event.get("affected_nodes", []))
            teams = teams_df[teams_df["base_node"].isin(affected_nodes)][["unit_id", "name", "base_node"]]
            st.dataframe(teams, use_container_width=True)
    if st.button("Trigger Disaster", key="trigger_disaster"):
        new_ev = spread_disaster(G, epicenter, radius, dtype.lower(), severity.lower())
        events.append(new_ev)
        save_disaster_events(events, active_city)
        st.success(
            f"{len(new_ev.get('blocked_edges', []))} roads blocked, "
            f"{len(new_ev.get('affected_nodes', []))} nodes affected"
        )
        st.rerun()

    st.markdown("### Stranded Population Control")
    active_affected_nodes = sorted({nid for e in active_events for nid in e.get("affected_nodes", [])})
    if not active_affected_nodes:
        st.info("No active disaster nodes. Trigger a disaster first, then set stranded people.")
    else:
        node_map = {n["id"]: n for n in city.get("nodes", [])}
        changed = False
        for nid in active_affected_nodes:
            node = node_map.get(nid, {})
            cur = int(node.get("people_stranded", 0))
            row_left, row_right = st.columns([0.68, 0.32], gap="small")
            row_left.markdown(f"**{node_id_to_name.get(nid, nid)}** (`{nid}`)")
            with row_right:
                new_val = st.slider(
                    "Stranded",
                    min_value=0,
                    max_value=1000,
                    value=cur,
                    step=10,
                    key=f"stranded_{nid}",
                    label_visibility="collapsed",
                )
            if new_val != cur:
                node["people_stranded"] = int(new_val)
                changed = True
        if changed:
            save_city_graph(city, active_city)
            st.toast("Stranded population updated.")

    st.markdown("### Active Disasters")
    for i, ev in enumerate(active_events):
        with st.expander(f"{ev.get('type', '').title()} - {ev.get('severity', '').title()} - {ev.get('timestamp', '')}", expanded=False):
            st.write(f"Epicenter: {ev.get('affected_nodes', [''])[0] if ev.get('affected_nodes') else ''}")
            affected = ev.get("affected_nodes", [])
            preview_nodes = ", ".join(affected[:5]) + (f" + {len(affected)-5} more" if len(affected) > 5 else "")
            st.write(f"Affected nodes: {preview_nodes}")
            st.write(f"Blocked roads: {len(ev.get('blocked_edges', []))}")
            new_sev = st.select_slider(
                "Change Severity",
                ["low", "medium", "high", "critical"],
                value=str(ev.get("severity", "low")).lower(),
                key=f"severity_{i}",
            )
            partial = st.slider("Restore X% of blocked roads", 0, 100, 0, key=f"partial_{i}")
            c1, c2, c3 = st.columns(3)
            if c1.button("Spread +1 hop further", key=f"spread_more_{i}") and affected:
                ext = spread_disaster(G, affected[0], 1, ev.get("type", "flood"), new_sev)
                ev["affected_nodes"] = sorted(set(ev.get("affected_nodes", []) + ext.get("affected_nodes", [])))
                ev["blocked_edges"] = [list(x) for x in {tuple(sorted(x)) for x in (ev.get("blocked_edges", []) + ext.get("blocked_edges", []))}]
            if c2.button("Apply Changes", key=f"apply_{i}"):
                ev["severity"] = new_sev
                if partial > 0 and ev.get("blocked_edges"):
                    keep = int(len(ev["blocked_edges"]) * (100 - partial) / 100)
                    random.shuffle(ev["blocked_edges"])
                    ev["blocked_edges"] = ev["blocked_edges"][:keep]
                save_disaster_events(events, active_city)
                st.rerun()
            if c3.button("Mark as Resolved", key=f"resolve_{i}"):
                ev["active"] = False
                ev["resolved_at"] = datetime.now().isoformat(timespec="seconds")
                save_disaster_events(events, active_city)
                st.rerun()

    st.markdown("### Manual Road Management")
    left, right = st.columns(2)
    with left:
        node_a = st.selectbox("Select Node A", sorted(node_id_to_name), key="manual_a")
        nbrs = sorted(G.neighbors(node_a))
        node_b = st.selectbox("Select Node B", nbrs, key="manual_b")
        reason = st.text_input("Reason", key="manual_reason")
        if st.button("Block Road", key="manual_block"):
            save_disaster_events(block_road(node_a, node_b, reason, events), active_city)
            mm = MissionManager()
            active_missions = [m for m in mm.load() if m.get("city") == active_city and m.get("status") != "complete"]
            affected = block_road_live(G, node_a, node_b, active_missions).get("affected_missions", [])
            if affected:
                st.warning(f"Affected missions: {', '.join(affected)}")
                for mission_id in affected:
                    if st.button(f"Replan Mission {mission_id}", key=f"replan_{mission_id}"):
                        from core.graph_engine import get_positions

                        city_graph = load_city_graph(active_city)
                        mm.replan_mission(mission_id, load_graph(city_graph), events, get_positions(city_graph), city_graph)
            st.rerun()
    with right:
        blocked_opts = [f"{u} - {v}" for u, v in sorted(blocked)]
        selected = st.selectbox("Blocked Roads", blocked_opts if blocked_opts else ["None"], key="manual_restore_select")
        if st.button("Restore Road", key="manual_restore") and selected != "None":
            u, v = selected.split(" - ")
            save_disaster_events(unblock_road(u, v, events), active_city)
            st.rerun()

    st.markdown("### Disaster History")
    resolved = [e for e in events if not e.get("active", True)]
    rows = []
    for ev in resolved:
        rows.append(
            {
                "Type": ev.get("type", "").title(),
                "Severity": ev.get("severity", "").title(),
                "Duration (ticks)": 0,
                "Roads Blocked": len(ev.get("blocked_edges", [])),
                "Resolved At": ev.get("resolved_at", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

