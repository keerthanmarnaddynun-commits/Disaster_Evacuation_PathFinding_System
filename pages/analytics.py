"""Algorithm analytics, benchmarks, and scheduling comparison."""

from __future__ import annotations

import copy
import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from algorithms.Astar import astar, euclidean_distance
from algorithms.Dijkstra import dijkstra
from algorithms.ant_colony import ant_colony_optimization
from algorithms.bidirectional_search import bidirectional_dijkstra
from algorithms.bfs import bfs
from algorithms.dfs import dfs
from algorithms.dstar_lite import dstar_lite_path
from algorithms.greedy_best_first import greedy_best_first
from algorithms.ucs import ucs

from core import data_loader, disaster_manager, evacuation_planner, graph_engine
from core.interval_scheduler import RescueScheduler, load_missions_from_disk
from utils import app_state


def _run_algo(
    name: str,
    s: str,
    g: str,
    w_fast: dict,
    w_bal: dict,
    unw: dict,
    pos: dict,
) -> dict:
    """Returns dict with cost, time_ms, path_ok."""
    t0 = time.perf_counter()
    path = None
    cost = float("inf")
    try:
        if name == "BFS":
            path = bfs(unw, s, g)
            cost = float(len(path) - 1) if path else float("inf")
        elif name == "DFS":
            path = dfs(unw, s, g)
            cost = float(len(path) - 1) if path else float("inf")
        elif name == "Dijkstra":
            path, cost = dijkstra(w_bal, s, g)
        elif name == "UCS":
            path, cost = ucs(w_bal, s, g)
        elif name == "A*":
            path, cost = astar(w_fast, s, g, euclidean_distance, pos)
        elif name == "Greedy BFS":
            path, cost = greedy_best_first(w_fast, s, g, euclidean_distance, pos)
        elif name == "Bidirectional Dijkstra":
            path, cost = bidirectional_dijkstra(w_bal, s, g)
        elif name == "D* Lite":
            path, cost = dstar_lite_path(w_bal, s, g, pos)
        elif name == "ACO":
            path, cost = ant_colony_optimization(w_bal, s, g, pos, n_ants=10, n_iterations=15)
        else:
            path, cost = None, float("inf")
    except Exception:
        path, cost = None, float("inf")
    dt = (time.perf_counter() - t0) * 1000.0
    ok = path is not None and cost != float("inf")
    return {"cost": float(cost) if ok else float("inf"), "time_ms": dt, "ok": ok, "path": path}


def render() -> None:
    st.header("Algorithm Analytics")

    tab_main, tab_bench, tab_sched = st.tabs(
        ["Disaster progression", "Algorithm benchmark", "Scheduling analysis"]
    )

    G_full = graph_engine.load_graph()
    events = data_loader.read_disaster_events()

    with tab_main:
        st.subheader("Legacy benchmark (all pairs × 4 classic algorithms)")
        safe_nodes = [z["node_id"] for z in data_loader.read_safe_zones()]
        sources = sorted(G_full.nodes())
        pairs = [(s, g) for s in sources for g in safe_nodes if s != g]
        mode = st.selectbox(
            "Weight mode for legacy benchmark",
            ["fastest", "safest", "balanced"],
            format_func=lambda x: x.title(),
            key="legacy_mode",
        )

        if st.button("Run full benchmark (all pairs × 4 algorithms)", type="primary", key="legacy_btn"):
            stats = {"BFS": [], "DFS": [], "Dijkstra": [], "A*": []}
            times = {"BFS": [], "DFS": [], "Dijkstra": [], "A*": []}
            failed = {k: 0 for k in stats}
            cpu = {k: 0.0 for k in stats}

            progress = st.progress(0.0)
            total = len(pairs) * 4
            done = 0
            for s, g in pairs:
                for name in ["BFS", "DFS", "Dijkstra", "A*"]:
                    G = app_state.get_city_graph()
                    t0 = time.perf_counter()
                    r = evacuation_planner.plan_route(G, s, g, name, mode, active_events=events)
                    dt = time.perf_counter() - t0
                    cpu[name] += dt
                    c = r.get("weighted_cost", float("inf"))
                    if r.get("path") is None or c == float("inf"):
                        failed[name] += 1
                    else:
                        stats[name].append(float(c))
                        times[name].append(float(r.get("estimated_time", 0) or 0))
                    done += 1
                    progress.progress(done / total)

            rows = []
            for name in stats:
                arr = stats[name]
                arr_t = times[name]
                rows.append(
                    {
                        "algorithm": name,
                        "avg_path_cost": float(np.mean(arr)) if arr else None,
                        "avg_time_min": float(np.mean(arr_t)) if arr_t else None,
                        "avg_cpu_sec_per_query": cpu[name] / max(len(pairs), 1),
                        "paths_found": len(arr),
                        "failed_queries": failed[name],
                    }
                )
            st.dataframe(rows, use_container_width=True)

            fig = go.Figure()
            for name in stats:
                arr = stats[name]
                if arr:
                    fig.add_trace(go.Bar(name=name, x=[name], y=[float(np.mean(arr))]))
            fig.update_layout(
                title="Average path cost by algorithm",
                paper_bgcolor="#020617",
                plot_bgcolor="#0f172a",
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Disaster progression (path cost vs. blocked edges)")
        if st.button("Compute progression chart", key="prog_btn"):
            base = graph_engine.load_graph()
            order = list(base.edges())
            np.random.seed(42)
            np.random.shuffle(order)
            mode2 = st.session_state.get("legacy_mode", "balanced")

            xs = []
            series = {name: [] for name in ["Dijkstra", "A*"]}
            start, goal = "N001", "N025"
            ev = data_loader.read_disaster_events()
            blocked = disaster_manager.collect_blocked_edges(ev)
            for n_block in range(0, min(20, len(order) + 1), 2):
                extra = set()
                for i in range(min(n_block, len(order))):
                    u, v = order[i]
                    a, b = (u, v) if u <= v else (v, u)
                    extra.add((a, b))
                H = base.copy()
                for u, v in list(H.edges()):
                    key = (u, v) if u <= v else (v, u)
                    if key in blocked or key in extra:
                        H.remove_edge(u, v)
                xs.append(n_block)
                for name in ["Dijkstra", "A*"]:
                    r = evacuation_planner.plan_route(H, start, goal, name, mode2, active_events=ev)
                    c = r.get("weighted_cost", float("inf"))
                    series[name].append(float(c) if c != float("inf") else np.nan)

            fig2 = go.Figure()
            for name, ys in series.items():
                fig2.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=name))
            fig2.update_layout(
                title="Cost as more roads blocked (synthetic progression)",
                xaxis_title="Extra blocked edges (shuffled)",
                yaxis_title="Weighted cost",
                paper_bgcolor="#020617",
                plot_bgcolor="#0f172a",
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.caption(
            "Under high disaster load, Dijkstra and A* typically track closely; "
            "BFS/DFS ignore weights and are omitted from the progression chart."
        )

    with tab_bench:
        st.subheader("Extended algorithm benchmark (5 fixed pairs)")
        fixed_pairs = [
            ("N001", "N005"),
            ("N006", "N012"),
            ("N013", "N018"),
            ("N019", "N025"),
            ("N030", "N012"),
        ]
        st.write("Pairs:", fixed_pairs)
        if st.button("Run extended benchmark", type="primary", key="ext_bench"):
            G = app_state.get_city_graph()
            events_l = data_loader.read_disaster_events()
            w_fast = graph_engine.to_weighted_adjacency(G, "fastest", active_events=events_l)
            w_bal = graph_engine.to_weighted_adjacency(G, "balanced", active_events=events_l)
            unw = graph_engine.to_unweighted_adjacency(G)
            pos = graph_engine.node_positions(G)

            algos = [
                "BFS",
                "DFS",
                "Dijkstra",
                "UCS",
                "A*",
                "Greedy BFS",
                "Bidirectional Dijkstra",
                "D* Lite",
                "ACO",
            ]
            rows = []
            ref_per_pair: list[float] = []
            for s, g in fixed_pairs:
                p_ref, c_ref = dijkstra(w_bal, s, g)
                ref_per_pair.append(float(c_ref) if p_ref else float("inf"))

            for name in algos:
                costs: list[float] = []
                tms: list[float] = []
                oks = 0
                ratios: list[float] = []
                for i, (s, g) in enumerate(fixed_pairs):
                    r = _run_algo(name, s, g, w_fast, w_bal, unw, pos)
                    tms.append(r["time_ms"])
                    ref = ref_per_pair[i]
                    if r["ok"]:
                        oks += 1
                        costs.append(r["cost"])
                        if ref != float("inf") and ref > 0:
                            ratios.append(r["cost"] / ref)
                avg_c = float(np.mean(costs)) if costs else None
                avg_t = float(np.mean(tms)) if tms else None
                succ = oks / len(fixed_pairs)
                opt_rat = float(np.mean(ratios)) if ratios else None
                rows.append(
                    {
                        "algorithm": name,
                        "avg_cost": avg_c,
                        "avg_time_ms": avg_t,
                        "success_rate": succ,
                        "optimality_ratio": opt_rat,
                    }
                )

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)

            figb = px.bar(df, x="algorithm", y="avg_time_ms", title="Execution time (ms)")
            figb.update_layout(paper_bgcolor="#020617", plot_bgcolor="#0f172a", font=dict(color="#e2e8f0"))
            st.plotly_chart(figb, use_container_width=True)

            figs = px.scatter(
                df,
                x="avg_cost",
                y="avg_time_ms",
                color="algorithm",
                title="Path cost vs execution time",
            )
            figs.update_layout(paper_bgcolor="#020617", plot_bgcolor="#0f172a", font=dict(color="#e2e8f0"))
            st.plotly_chart(figs, use_container_width=True)

    with tab_sched:
        st.subheader("Compare scheduling strategies")
        missions0 = load_missions_from_disk()
        units = data_loader.read_rescue_units()
        G = app_state.get_city_graph()
        if st.button("Compare strategies", key="cmp_sched"):
            rows = []
            for strat in ["priority_first", "maximize_missions", "maximize_people"]:
                missions = copy.deepcopy(missions0)
                sched = RescueScheduler(missions, units, G=G)
                sched.schedule(strategy=strat, persist=False)
                stt = sched.get_statistics()
                crit_left = int(stt.get("critical_unscheduled", 0))
                crit_total = sum(1 for m in missions0 if m.priority == 1)
                crit_handled = max(0, crit_total - crit_left)
                rows.append(
                    {
                        "strategy": strat,
                        "missions_scheduled": stt["total_missions_scheduled"],
                        "people_rescued": stt["total_people_scheduled"],
                        "critical_missions_handled": crit_handled,
                    }
                )
            sdf = pd.DataFrame(rows)
            st.dataframe(sdf, use_container_width=True)


if __name__ == "__main__":
    render()
