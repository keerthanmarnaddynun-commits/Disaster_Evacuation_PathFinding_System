from __future__ import annotations

import heapq

import pandas as pd
import plotly.express as px
import streamlit as st

from core.algorithm_selector import select_and_run
from core.data_loader import load_city_graph, load_disaster_events, load_rescue_log_df, load_rescue_units_df
from core.dynamic_obstacles import block_road_live
from core.graph_engine import get_positions, load_graph
from core.greedy_selector import nearest_team_to_target
from core.knapsack import build_victim_list, knapsack_01
from core.mission_manager import MissionManager
from core.data_loader import save_disaster_events
from utils.visualizer import build_city_map


def _badge(status: str) -> str:
    color = {"en_route": "#ebcb8b", "arrived": "#88c0d0", "rescued": "#81a1c1", "returning": "#5e81ac", "complete": "#8fbcbb"}.get(status, "#4c566a")
    return f"<span style='background:{color};color:#fff;border-radius:999px;padding:3px 10px;font-weight:700;'>{status}</span>"


def render():
    city = st.session_state.get("active_city", "Veridian City")
    city_data = load_city_graph(city)
    events = load_disaster_events(city)
    units_df = load_rescue_units_df(city)
    nodes_df = pd.DataFrame(city_data.get("nodes", []))
    node_map = {n["id"]: n for n in city_data.get("nodes", [])}
    node_name = {n["id"]: n["id"] for n in city_data.get("nodes", [])}
    G = load_graph(city_data)
    positions = get_positions(city_data)
    mm = MissionManager()

    st.title("Rescue Operations Center")
    st.caption(city)

    st.subheader("Team Status Overview")
    teams = units_df.copy()
    teams["fuel_pct"] = (teams["fuel_remaining"] / teams["fuel_capacity"]) * 100
    team_status_df = teams.rename(
        columns={
            "name": "Team",
            "unit_type": "Type",
            "current_node": "Current Location",
            "status": "Status",
            "fuel_pct": "Fuel %",
            "medical_kits": "Kits",
            "total_rescued": "Rescued",
        }
    )[["Team", "Type", "Current Location", "Status", "Fuel %", "Kits", "Rescued"]]
    team_status_styler = team_status_df.style.map(
        lambda v: "background-color:#e74c3c;" if isinstance(v, (int, float)) and v < 20 else "",
        subset=["Fuel %"],
    )
    st.dataframe(team_status_styler, use_container_width=True)

    st.subheader("Active Missions")
    active = [m for m in mm.load() if m.get("status") in {"en_route", "arrived", "returning", "rescued"} and m.get("city") == city]
    rescued_active = [m for m in active if m.get("status") == "rescued"]
    if rescued_active and st.button("Clear All Settled Missions"):
        for m in rescued_active:
            mm.complete_mission(m["mission_id"])
        st.rerun()
    if not active:
        st.info("No active missions. Dispatch a team below.")
    for m in active:
        with st.container(border=True):
            st.markdown(f"**{m['mission_id']} | {m['team_name']} ({m['team_type']}) | {m['algorithm_used']}** &nbsp;&nbsp; {_badge(m['status'])}", unsafe_allow_html=True)
            cur = m["current_step"]
            total = max(1, len(m["path"]) - 1)
            st.progress(cur / total, text=f"Step {cur} of {total} — At: {m['path_names'][cur]}")
            visited = m["path"][: cur + 1]
            remaining = m["path"][cur:]
            highlights = [
                {"path": visited, "color": "#8fbcbb", "width": 5, "label": "Visited", "dash": "solid", "show_steps": True},
                {"path": remaining, "color": "#81a1c1", "width": 4, "label": "Remaining", "dash": "dot", "show_steps": False},
            ]
            st.plotly_chart(build_city_map(city_data, highlight_paths=highlights, show_labels=False), use_container_width=True)
            if m["status"] in {"en_route", "returning"}:
                if st.button("Advance One Step", key=f"adv_{m['mission_id']}"):
                    mm.advance_step(m["mission_id"])
                    st.rerun()
                with st.expander("Block a Road"):
                    all_edges = sorted({tuple(sorted((e["source"], e["target"]))) for e in city_data.get("edges", [])})
                    selected = st.selectbox("Select road to block", all_edges, key=f"blk_{m['mission_id']}")
                    if st.button("Block Selected Road", key=f"doblk_{m['mission_id']}"):
                        out = block_road_live(G, selected[0], selected[1], active)
                        if m["mission_id"] in out["affected_missions"]:
                            old_steps = len(m["path"]) - 1
                            old_algo = m["algorithm_used"]
                            new_m = mm.replan_mission(m["mission_id"], G, events, positions, city_data)
                            st.warning(f"This mission's path is now invalid. Replanned from {old_steps} steps via {old_algo} to {len(new_m['path'])-1} via {new_m['algorithm_used']}.")
                            st.rerun()
            elif m["status"] == "arrived":
                st.info(f"Team has arrived at {m['target_name']}. {m['people_at_target']} people waiting. Injury: {m['injury_level']}")
                if st.button(f"Confirm Rescue ({m['people_at_target']} people)", key=f"rescue_{m['mission_id']}"):
                    try:
                        mm.confirm_rescue(m["mission_id"], m["people_at_target"])
                    except ValueError as ex:
                        st.error(str(ex))
                    st.rerun()
            elif m["status"] == "rescued":
                st.info(f"Rescue complete. Transport survivors to safe zone: {m.get('safe_zone_name', 'Safe Zone')}")
                if st.button("Start Return Journey", key=f"ret_{m['mission_id']}"):
                    mm.start_return(m["mission_id"])
                    st.rerun()
                if st.button("Close Mission (Already Settled)", key=f"close_{m['mission_id']}"):
                    mm.complete_mission(m["mission_id"])
                    st.success(f"{m['mission_id']} marked complete.")
                    st.rerun()

    st.subheader("Dispatch Rescue Team")
    left, right = st.columns([1, 1.2])
    active_affected = {n for e in events if e.get("active", False) for n in e.get("affected_nodes", [])}
    victims = nodes_df[(nodes_df["id"].isin(active_affected)) & (nodes_df["people_stranded"] > 0)].copy().sort_values("people_stranded", ascending=False)
    if victims.empty:
        st.info("No currently stranded people in active disaster nodes. Use Disaster Control to set stranded population.")
        return
    available = units_df[units_df["status"] == "available"].copy()
    if available.empty:
        st.warning("No available teams to dispatch.")
        return
    team_capacity_budget = int(available["capacity"].sum())
    intro = build_victim_list(city_data, victims["id"].tolist(), events)
    knapsack_out = knapsack_01(intro, team_capacity_budget)
    selected_nodes = {row["node_id"] for row in knapsack_out["selected"]}
    if selected_nodes:
        victims = victims[victims["id"].isin(selected_nodes)].copy()
    pq = []
    for _, row in victims.iterrows():
        severity_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(row.get("injury_level", "low")).lower(), 1)
        priority = -(severity_weight * int(row.get("people_stranded", 0)))
        heapq.heappush(pq, (priority, row["id"]))
    top_node = pq[0][1] if pq else victims.iloc[0]["id"]
    with left:
        st.caption("Priority Queue (higher severity and stranded people first)")
        queue_preview = [{"rank": i + 1, "node": node_name[n], "node_id": n} for i, (_, n) in enumerate(sorted(pq)[:10])]
        st.dataframe(queue_preview, use_container_width=True, hide_index=True)
        tgt = st.selectbox(
            "Target Node",
            victims["id"].tolist(),
            index=victims["id"].tolist().index(top_node),
            format_func=lambda n: f"{node_name.get(n, n)}",
        )
        strategy = st.radio("Recommendation Strategy", ["Nearest team to target", "Highest priority team (best fuel + kits)"])
        unit_types = {r["unit_id"]: ("helicopter" if r["unit_type"] == "helicopter" else "ground") for _, r in available.iterrows()}
        rec = nearest_team_to_target(G, tgt, available.to_dict(orient="records"), events, unit_types) if strategy.startswith("Nearest") else {}
        default_team = rec.get("team", {}).get("unit_id") if rec else available.iloc[0]["unit_id"]
        team_id = st.selectbox("Select Team", available["unit_id"].tolist(), index=available["unit_id"].tolist().index(default_team))
        team = available[available["unit_id"] == team_id].iloc[0]

    with right:
        unit_mode = "helicopter" if team["unit_type"] == "helicopter" else "ground"
        out = select_and_run(G, team["current_node"], tgt, events, positions, city_data, unit_type=unit_mode)
        df = pd.DataFrame(out["all_results"])
        if not df.empty:
            df["Air Route"] = df["used_air_edges"].map(lambda v: "AIR" if v else "Road")
            st.dataframe(df[["Algorithm", "Path Found", "Path Length", "Nodes Explored", "Time (ms)", "Safety Score", "Air Route"]], use_container_width=True)
            c1, c2, c3 = st.columns(3)
            for col, c in [("Nodes Explored", c1), ("Time (ms)", c2), ("Path Length", c3)]:
                fig = px.bar(df, x=col, y="Algorithm", orientation="h", template="plotly_dark")
                c.plotly_chart(fig, use_container_width=True)
            rec_path = out["recommended"]["path"]
            hp = [{"path": rec_path, "color": "#88c0d0", "width": 4, "label": f"{out['recommended']['algorithm']} path", "dash": "solid", "show_steps": True}]
            st.plotly_chart(build_city_map(city_data, highlight_paths=hp, show_labels=False), use_container_width=True)
            st.caption(f"{out['recommended']['algorithm']} — {out['recommended']['why_selected']} Teams begin from safe zones and return survivors to nearest safe zone.")
            override = st.selectbox("Use different algorithm", ["Recommended"] + df["Algorithm"].tolist())
            selected_algo = out["recommended"]["algorithm"] if override == "Recommended" else override
            btn = st.button(f"Dispatch {team['name']} via {selected_algo}")
            if btn:
                algo_row = next((r for r in out["all_results"] if r["Algorithm"] == selected_algo), out["recommended"])
                path = algo_row["Path"] if "Path" in algo_row else out["recommended"]["path"]
                result_meta = {
                    "algorithm": selected_algo,
                    "why_selected": out["recommended"]["why_selected"],
                    "nodes_explored": int(algo_row.get("Nodes Explored", out["recommended"]["nodes_explored"])),
                    "runtime_ms": float(algo_row.get("Time (ms)", out["recommended"]["runtime_ms"])),
                    "used_air_edges": bool(algo_row.get("used_air_edges", out["recommended"]["used_air_edges"])),
                }
                mission = mm.create_mission(
                    team.to_dict(),
                    tgt,
                    node_name[tgt],
                    path,
                    [node_name.get(n, n) for n in path],
                    result_meta,
                    int(victims[victims["id"] == tgt]["people_stranded"].iloc[0]),
                    victims[victims["id"] == tgt]["injury_level"].iloc[0] if "injury_level" in victims else "high",
                    city,
                )
                st.success(f"Mission {mission['mission_id']} created. Team {team['name']} dispatched to {node_name[tgt]}.")
                st.rerun()

    with st.expander("Knapsack Optimization — Prioritize Rescue Targets"):
        cap = int(available["capacity"].sum())
        out = knapsack_01(intro, cap)
        st.dataframe(pd.DataFrame(intro), use_container_width=True)
        st.dataframe(pd.DataFrame(out["dp_table"]).style.background_gradient(cmap="Blues"), use_container_width=True)
        st.dataframe(pd.DataFrame(out["selected"]), use_container_width=True)

    with st.expander("Rescue Log"):
        log_df = load_rescue_log_df()
        st.dataframe(log_df, use_container_width=True)
    city_rescue_log = load_rescue_log_df()
    if not city_rescue_log.empty:
        city_rescue_log = city_rescue_log[city_rescue_log["city"] == city]
    open_events = [e for e in events if e.get("active", False)]
    unresolved_stranded = int(nodes_df["people_stranded"].sum()) if not nodes_df.empty else 0
    if not active and unresolved_stranded == 0 and not city_rescue_log.empty:
        total_people = int(city_rescue_log["people_rescued"].fillna(0).sum())
        avg_nodes = float(city_rescue_log["nodes_explored"].fillna(0).mean())
        avg_time = float(city_rescue_log["time_ms"].fillna(0).mean())
        optimality = max(0.0, min(100.0, 100.0 - (avg_nodes * 2.0 + (avg_time / 10.0))))
        st.success("Successful rescue mission campaign completed.")
        c1, c2, c3 = st.columns(3)
        c1.metric("People Rescued", total_people)
        c2.metric("Avg Nodes Explored", f"{avg_nodes:.1f}")
        c3.metric("Optimality Score", f"{optimality:.1f}/100")
        if open_events and st.button("Resolve All Active Disasters"):
            for e in events:
                if e.get("active", False):
                    e["active"] = False
                    e["resolved_at"] = pd.Timestamp.now().isoformat()
            save_disaster_events(events, city)
            st.rerun()

