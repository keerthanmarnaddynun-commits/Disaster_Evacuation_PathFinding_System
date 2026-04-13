from __future__ import annotations

import math
import time

import pandas as pd

from algorithms.astar import astar, euclidean_distance
from algorithms.bfs import bfs
from algorithms.dfs import dfs
from algorithms.dijkstra import dijkstra
from algorithms.ucs import ucs
from core.disaster_manager import compute_risk_score
from core.graph_engine import get_adjacency_list, get_unweighted_adjacency


def _run_algorithm(name: str, fn, *args):
    t0 = time.perf_counter()
    out = fn(*args)
    t1 = time.perf_counter()
    return out, (t1 - t0) * 1000.0, name


def _path_uses_air(G, path: list[str]) -> bool:
    for i in range(len(path) - 1):
        if bool(G.edges[path[i], path[i + 1]].get("air_only", False)):
            return True
    return False


def select_and_run(
    G,
    start: str,
    goal: str,
    disaster_events: list,
    positions: dict,
    city_graph_data: dict,
    unit_type: str = "ground",
) -> dict:
    adj_unweighted = get_unweighted_adjacency(G, disaster_events, unit_type=unit_type)
    adj_weighted = get_adjacency_list(G, "balanced", disaster_events, unit_type=unit_type)
    adj_safest = get_adjacency_list(G, "safest", disaster_events, unit_type=unit_type)

    runs = []
    bfs_path, bfs_ms, _ = _run_algorithm("BFS", bfs, adj_unweighted, start, goal)
    dfs_path, dfs_ms, _ = _run_algorithm("DFS", dfs, adj_unweighted, start, goal)
    (dij_path, dij_cost), dij_ms, _ = _run_algorithm("Dijkstra", dijkstra, adj_weighted, start, goal)
    (ast_path, ast_cost), ast_ms, _ = _run_algorithm("A*", astar, adj_safest, start, goal, euclidean_distance, positions)
    (ucs_path, ucs_cost), ucs_ms, _ = _run_algorithm("UCS", ucs, adj_weighted, start, goal)

    runs.extend(
        [
            {"algorithm": "BFS", "path": bfs_path or [], "cost": float(len(bfs_path) - 1) if bfs_path else math.inf, "time_ms": bfs_ms},
            {"algorithm": "DFS", "path": dfs_path or [], "cost": float(len(dfs_path) - 1) if dfs_path else math.inf, "time_ms": dfs_ms},
            {"algorithm": "Dijkstra", "path": dij_path or [], "cost": float(dij_cost), "time_ms": dij_ms},
            {"algorithm": "A*", "path": ast_path or [], "cost": float(ast_cost), "time_ms": ast_ms},
            {"algorithm": "UCS", "path": ucs_path or [], "cost": float(ucs_cost), "time_ms": ucs_ms},
        ]
    )

    rows = []
    for run in runs:
        path = run["path"]
        found = len(path) > 0
        path_len = max(0, len(path) - 1) if found else 0
        nodes_explored = len(path) if found else 0
        risk_vals = [compute_risk_score(n, disaster_events, G) for n in path] if found else [1.0]
        safety = 1.0 - (sum(risk_vals) / len(risk_vals))
        rows.append(
            {
                "Algorithm": run["algorithm"],
                "Path Found": found,
                "Path": path,
                "Path Length": path_len,
                "Nodes Explored": nodes_explored,
                "Time (ms)": float(run["time_ms"]),
                "Travel Time (min)": float(run["cost"]) if math.isfinite(run["cost"]) else float("inf"),
                "Safety Score": float(max(0.0, safety)),
                "used_air_edges": _path_uses_air(G, path) if found else False,
            }
        )

    df = pd.DataFrame(rows)
    df["Composite Score"] = (
        df["Time (ms)"].rank(pct=True)
        + df["Nodes Explored"].rank(pct=True)
        + df["Path Length"].replace(0, math.inf).rank(pct=True)
        + (1.0 - df["Safety Score"]).rank(pct=True)
    )
    df.loc[~df["Path Found"], "Composite Score"] = float("inf")
    best_row = df.sort_values("Composite Score").iloc[0]

    all_results = df.sort_values("Composite Score").to_dict(orient="records")
    rec = {
        "algorithm": best_row["Algorithm"],
        "path": best_row["Path"],
        "travel_time_min": float(best_row["Travel Time (min)"]),
        "safety_score": float(best_row["Safety Score"]),
        "nodes_explored": int(best_row["Nodes Explored"]),
        "path_length": int(best_row["Path Length"]),
        "runtime_ms": float(best_row["Time (ms)"]),
        "used_air_edges": bool(best_row["used_air_edges"]),
        "composite_score": float(best_row["Composite Score"]),
        "why_selected": "Lowest composite score across time, exploration count, path length, and safety.",
    }
    return {"recommended": rec, "all_results": all_results, "all_results_df": df}

