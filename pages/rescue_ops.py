"""Rescue coordination UI + mission scheduling."""

from __future__ import annotations

import uuid

import pandas as pd
import plotly.express as px
import streamlit as st

from core import data_loader, evacuation_planner, rescue_coordinator
from core.interval_scheduler import RescueMission, RescueScheduler, load_missions_from_disk
from utils import app_state


def render() -> None:
    st.header("Rescue Coordination")
    G = app_state.get_city_graph()
    units = rescue_coordinator.load_units()
    zones = data_loader.read_evacuation_zones()
    safe = data_loader.read_safe_zones()

    st.subheader("Rescue units")
    st.dataframe(units, use_container_width=True)

    zone_labels = {f"{z['name']} ({z['zone_id']})": z for z in zones}
    pick = st.selectbox("Zone in distress", list(zone_labels.keys()))
    zone = zone_labels[pick]

    wadj_mode = st.selectbox("Dispatch weight mode", ["fastest", "balanced"], format_func=lambda x: x.title())

    rec = rescue_coordinator.get_optimal_dispatch(G, units, zone, mode=wadj_mode)
    if rec:
        st.info(f"Recommended unit: **{rec['name']}** ({rec['unit_id']}) at `{rec['location_node']}`")
    else:
        st.warning("No available unit found.")

    people = st.number_input("People evacuated (log)", min_value=0, value=10, step=1)

    if st.button("Dispatch recommended unit", type="primary") and rec:
        path_result = evacuation_planner.plan_route(
            G,
            rec["location_node"],
            zone["nodes"][0],
            "Dijkstra",
            wadj_mode,
            active_events=data_loader.read_disaster_events(),
        )
        path = path_result.get("path") or []
        cost = float(path_result.get("weighted_cost", 0) or 0)
        rescue_coordinator.assign_unit(
            G,
            rec,
            zone["zone_id"],
            algorithm_used="dijkstra",
            route_path=path,
            total_cost=cost,
            people=int(people),
            status="deployed",
        )
        app_state.refresh_base_graph()
        st.success("Dispatch logged.")
        st.rerun()

    st.subheader("Mission Scheduler")
    missions = load_missions_from_disk()
    st.caption("Missions persist to `data/rescue_missions.json`.")

    with st.form("new_mission"):
        st.write("Add mission")
        zid = st.selectbox("Zone", [z["zone_id"] for z in zones], key="ms_zone")
        t0 = st.number_input("Start time (min from onset)", 0.0, 10000.0, 0.0)
        t1 = st.number_input("End time (min from onset)", 0.0, 10000.0, 60.0)
        pr = st.selectbox("Priority", [1, 2, 3, 4], format_func=lambda x: f"{x} ({'critical' if x==1 else 'high' if x==2 else 'medium' if x==3 else 'low'})")
        pc = st.number_input("People count", 1, 100000, 50)
        ut = st.selectbox("Required unit type", ["any", "ambulance", "fire", "police"])
        submitted = st.form_submit_button("Add mission to queue")
        if submitted:
            mid = f"M-{uuid.uuid4().hex[:8].upper()}"
            missions.append(
                RescueMission(
                    mission_id=mid,
                    zone=zid,
                    start_time=float(t0),
                    end_time=float(t1),
                    priority=int(pr),
                    people_count=int(pc),
                    required_unit_type=str(ut),
                    assigned_unit=None,
                    status="pending",
                )
            )
            from core.interval_scheduler import persist_missions

            persist_missions(missions)
            st.success("Mission saved.")
            st.rerun()

    strat = st.selectbox(
        "Scheduling strategy",
        ["priority_first", "maximize_missions", "maximize_people"],
        format_func=lambda x: {
            "priority_first": "Priority First",
            "maximize_missions": "Maximize Missions",
            "maximize_people": "Maximize People Rescued",
        }[x],
    )

    if st.button("Run Scheduler", type="primary"):
        sched = RescueScheduler(missions, units, G=G)
        sched.schedule(strategy=strat)
        st.session_state["_last_sched"] = sched
        st.rerun()

    sched = st.session_state.get("_last_sched")
    if isinstance(sched, RescueScheduler):
        stats = sched.get_statistics()
        st.subheader("Schedule statistics")
        st.json(stats)

        crit = stats.get("critical_unscheduled", 0)
        if crit:
            st.error(f"Critical missions not scheduled: **{crit}**")

        tl = sched.get_schedule_timeline()
        rows = []
        for uid, blocks in tl.items():
            for b in blocks:
                rows.append(
                    {
                        "Unit": uid,
                        "Start": b["start_time"],
                        "Finish": b["end_time"],
                        "Mission": b["mission_id"],
                        "Zone": b["zone"],
                    }
                )
        if rows:
            tdf = pd.DataFrame(rows)
            fig = px.timeline(
                tdf,
                x_start="Start",
                x_end="Finish",
                y="Unit",
                color="Mission",
                hover_data=["Zone"],
            )
            fig.update_layout(
                title="Unit timelines",
                paper_bgcolor="#020617",
                plot_bgcolor="#0f172a",
                font=dict(color="#e2e8f0"),
                height=max(300, 80 * tdf["Unit"].nunique()),
            )
            st.plotly_chart(fig, use_container_width=True)

    if st.button("Re-optimize after road block"):
        missions2 = load_missions_from_disk()
        sched2 = RescueScheduler(missions2, rescue_coordinator.load_units(), G=app_state.get_city_graph())
        sched2.reoptimize()
        st.session_state["_last_sched"] = sched2
        st.success("Re-optimized.")
        st.rerun()

    st.subheader("Safe zone capacity")
    for z in safe:
        cap = int(z.get("capacity", 1))
        occ = int(z.get("current_occupancy", 0))
        st.progress(min(1.0, occ / max(cap, 1)), text=f"{z['name']}: {occ} / {cap}")

    st.subheader("Recent rescue log (last 20)")
    df = rescue_coordinator.generate_rescue_report()
    st.dataframe(df.tail(20), use_container_width=True)


if __name__ == "__main__":
    render()
