"""Route planning using algorithms.bfs, dfs, dijkstra, astar."""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Any

import networkx as nx

from algorithms.Astar import astar, euclidean_distance
from algorithms.Dijkstra import dijkstra, dijkstra_all_distances
from algorithms.bfs import bfs
from algorithms.dfs import dfs

from core import data_loader, graph_engine
from utils import metrics


def _time_call(fn):
    t0 = time.perf_counter()
    result = fn()
    dt = time.perf_counter() - t0
    return result, dt


def plan_route(
    G: nx.Graph,
    start: str,
    goal: str,
    algorithm: str,
    mode: str,
    *,
    active_events: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Returns path dict with keys: path, cost, estimated_time, safety_score, algorithm, compute_time_sec, weighted_cost.
    """
    events = active_events if active_events is not None else data_loader.read_disaster_events()
    algo = algorithm.lower().strip()

    if start not in G or goal not in G:
        return {
            "path": None,
            "cost": float("inf"),
            "estimated_time": float("inf"),
            "safety_score": 0.0,
            "algorithm": algorithm,
            "compute_time_sec": 0.0,
            "weighted_cost": float("inf"),
        }

    path: list[str] | None = None
    weighted_cost = float("inf")
    dt = 0.0

    if algo in ("bfs",):
        adj = graph_engine.to_unweighted_adjacency(G)

        def run_bfs():
            return bfs(adj, start, goal)

        path, dt = _time_call(run_bfs)
        if path:
            weighted_cost = float(len(path) - 1)

    elif algo in ("dfs",):
        adj = graph_engine.to_unweighted_adjacency(G)

        def run_dfs():
            return dfs(adj, start, goal)

        path, dt = _time_call(run_dfs)
        if path:
            weighted_cost = float(len(path) - 1)

    elif algo in ("dijkstra", "dijkstra's", "dijkstras"):
        wadj = graph_engine.to_weighted_adjacency(G, mode, active_events=events)

        def run_d():
            return dijkstra(wadj, start, goal)

        (path, weighted_cost), dt = _time_call(run_d)

    elif algo in ("a*", "astar", "a star"):
        wadj = graph_engine.to_weighted_adjacency(G, mode, active_events=events)
        pos = graph_engine.node_positions(G)

        def run_a():
            return astar(wadj, start, goal, euclidean_distance, pos)

        (path, weighted_cost), dt = _time_call(run_a)

    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    est_time = metrics.path_travel_time_minutes(G, path or [], active_events=events) if path else float("inf")
    safety = metrics.safety_score_path(G, path or [], active_events=events) if path else 0.0

    return {
        "path": path,
        "cost": weighted_cost if path else float("inf"),
        "estimated_time": est_time,
        "safety_score": safety,
        "algorithm": algorithm,
        "compute_time_sec": dt,
        "weighted_cost": weighted_cost if path else float("inf"),
    }


def compare_algorithms(
    G: nx.Graph,
    start: str,
    goal: str,
    mode: str,
    *,
    active_events: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Run BFS, DFS, Dijkstra, A*; return list of results sorted by weighted cost / hop count."""
    events = active_events if active_events is not None else data_loader.read_disaster_events()
    names = ["BFS", "DFS", "Dijkstra", "A*"]
    results: list[dict[str, Any]] = []
    for name in names:
        r = plan_route(G, start, goal, name, mode, active_events=events)
        results.append(r)

    def sort_key(r: dict) -> float:
        c = r.get("weighted_cost", float("inf"))
        if c == float("inf"):
            return 1e30
        return float(c)

    results.sort(key=sort_key)
    return results


def multi_source_evacuation(
    G: nx.Graph,
    sources: list[str],
    safe_zones: list[dict] | None = None,
    *,
    mode: str = "fastest",
    active_events: list[dict] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    For each source node, find lowest-cost route to any safe zone node (by Dijkstra).
    """
    events = active_events if active_events is not None else data_loader.read_disaster_events()
    sz = safe_zones if safe_zones is not None else data_loader.read_safe_zones()
    goal_nodes = {z["node_id"] for z in sz}

    wadj = graph_engine.to_weighted_adjacency(G, mode, active_events=events)
    out: dict[str, dict[str, Any]] = {}

    for src in sources:
        if src not in G:
            continue

        t0 = time.perf_counter()
        dists = dijkstra_all_distances(wadj, src)
        best_goal = None
        best_d = float("inf")
        for g in goal_nodes:
            if g in dists and dists[g] < best_d:
                best_d = dists[g]
                best_goal = g
        if best_goal is None:
            dt = time.perf_counter() - t0
            out[src] = {
                "path": None,
                "cost": float("inf"),
                "goal": None,
                "estimated_time": float("inf"),
                "safety_score": 0.0,
                "compute_time_sec": dt,
            }
            continue
        path, cost = dijkstra(wadj, src, best_goal)
        dt = time.perf_counter() - t0
        out[src] = {
            "path": path,
            "cost": cost,
            "goal": path[-1] if path else None,
            "estimated_time": metrics.path_travel_time_minutes(G, path or [], active_events=events)
            if path
            else float("inf"),
            "safety_score": metrics.safety_score_path(G, path or [], active_events=events) if path else 0.0,
            "compute_time_sec": dt,
        }
    return out


def get_alternative_routes(
    G: nx.Graph,
    start: str,
    goal: str,
    k: int = 3,
    *,
    mode: str = "balanced",
    active_events: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """
    Top-k distinct paths by penalizing edges used in prior paths (simple k-shortest variant).
    """
    events = active_events if active_events is not None else data_loader.read_disaster_events()
    base = graph_engine.to_weighted_adjacency(G, mode, active_events=events)
    wadj = deepcopy(base)
    results: list[dict[str, Any]] = []
    used_paths: list[list[str]] = []

    for _ in range(k):
        t0 = time.perf_counter()
        path, cost = dijkstra(wadj, start, goal)
        dt = time.perf_counter() - t0
        if path is None or cost == float("inf"):
            break
        if path in used_paths:
            break
        used_paths.append(path)
        results.append(
            {
                "path": path,
                "cost": cost,
                "estimated_time": metrics.path_travel_time_minutes(G, path, active_events=events),
                "safety_score": metrics.safety_score_path(G, path, active_events=events),
                "compute_time_sec": dt,
            }
        )
        # Penalize edges on this path to encourage diversity
        penalty = max(cost * 0.35, 2.0)
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            new_u: list[tuple[str, float]] = []
            for nb, w in wadj.get(u, []):
                if nb == v:
                    new_u.append((nb, w + penalty))
                else:
                    new_u.append((nb, w))
            wadj[u] = new_u
            new_v: list[tuple[str, float]] = []
            for nb, w in wadj.get(v, []):
                if nb == u:
                    new_v.append((nb, w + penalty))
                else:
                    new_v.append((nb, w))
            wadj[v] = new_v

    return results
