"""
Automatic algorithm + mode selection based on graph and disaster state.
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable

import networkx as nx

from algorithms.Astar import astar, euclidean_distance
from algorithms.Dijkstra import dijkstra
from algorithms.ant_colony import ant_colony_optimization
from algorithms.bidirectional_search import bidirectional_dijkstra
from algorithms.bfs import bfs
from algorithms.dstar_lite import DStarLite
from algorithms.greedy_best_first import greedy_best_first
from algorithms.ucs import ucs

from core import graph_engine
from core import dstar_runtime
from core.disaster_manager import compute_risk_score


def _timeout_run(fn: Callable[[], Any], seconds: float = 2.0) -> tuple[Any, float, bool]:
    """Returns (result, elapsed_sec, timed_out)."""
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            out = fut.result(timeout=seconds)
            dt = time.perf_counter() - t0
            return out, dt, False
        except FuturesTimeoutError:
            dt = time.perf_counter() - t0
            return None, dt, True


class AlgorithmSelector:
    """Picks best pathfinding result from multiple timed candidates."""

    TIMEOUT_SEC = 2.0

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        if not values:
            return []
        lo, hi = min(values), max(values)
        if math.isclose(hi, lo):
            return [0.5 for _ in values]
        return [(v - lo) / (hi - lo) for v in values]

    @staticmethod
    def _compute_path_risk(G: nx.Graph, path: list[str] | None, disaster_events: list[dict]) -> float:
        if not path:
            return 1.0
        risks = [compute_risk_score(n, disaster_events) for n in path]
        return sum(risks) / max(len(risks), 1)

    @staticmethod
    def _compute_congestion(G: nx.Graph, path: list[str] | None) -> float:
        if not path or len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if not G.has_edge(u, v):
                continue
            ed = G.edges[u, v]
            cap = max(float(ed.get("capacity", 1)), 1.0)
            load = float(ed.get("congestion_factor", 1.0))
            total += load / cap
        return total

    @staticmethod
    def _get_why_selected(algorithm: str, mode: str, scenario: dict[str, Any]) -> str:
        dp = float(scenario.get("disaster_pressure", 0))
        crit = scenario.get("critical_on_path", False)
        if "A*" in algorithm and "safest" in mode.lower():
            return (
                f"A* ({mode}) selected: high disaster pressure ({dp:.0%}) with "
                f"{'critical nodes on the corridor — prioritizing safety over raw speed.' if crit else 'elevated risk — safety-weighted routing.'}"
            )
        if "Dijkstra" in algorithm or "UCS" in algorithm:
            return f"{algorithm} ({mode}) selected: reliable shortest-path baseline under {dp:.0%} road stress."
        if "Bidirectional" in algorithm:
            return f"{algorithm} selected: larger search space or high pressure ({dp:.0%}) benefits from bidirectional exploration."
        if "Greedy" in algorithm:
            return f"{algorithm} selected: bridge/critical corridor — fast heuristic steering toward shelter."
        if "D*" in algorithm or "DStar" in algorithm:
            return f"{algorithm} selected: dynamic disaster stress ({dp:.0%}) — replanning-friendly search."
        if "Ant" in algorithm or "Colony" in algorithm:
            return f"{algorithm} selected: swarm exploration complements deterministic shortest paths."
        if "BFS" in algorithm:
            return f"{algorithm} selected: low disaster pressure — unweighted baseline is competitive."
        return f"{algorithm} ({mode}) selected: best composite score under current conditions."

    @classmethod
    def select_and_run(
        cls,
        G: nx.Graph,
        start: str,
        goal: str,
        disaster_events: list[dict],
        rescue_context: dict[str, Any],
    ) -> dict[str, Any]:
        _ = rescue_context
        active = [e for e in disaster_events if e.get("active", True)]
        blocked_count = sum(len(e.get("blocked_edges", [])) for e in active)
        n = max(G.number_of_nodes(), 1)
        m = G.number_of_edges()
        max_edges = n * (n - 1) / 2
        graph_density = m / max(max_edges, 1e-9)
        disaster_pressure = blocked_count / max(m, 1)

        w_bal = graph_engine.to_weighted_adjacency(G, "balanced", active_events=disaster_events)
        w_fast = graph_engine.to_weighted_adjacency(G, "fastest", active_events=disaster_events)
        w_safe = graph_engine.to_weighted_adjacency(G, "safest", active_events=disaster_events)
        unw = graph_engine.to_unweighted_adjacency(G)
        pos = graph_engine.node_positions(G)

        def default_shortest_path() -> list[str] | None:
            p, c = dijkstra(w_bal, start, goal)
            return p

        default_path = default_shortest_path()
        bridge_on_default = False
        critical_on_path = False
        if default_path:
            for nid in default_path:
                if G.nodes[nid].get("node_type") == "bridge":
                    bridge_on_default = True
                if compute_risk_score(nid, disaster_events) > 0.7:
                    critical_on_path = True

        results: list[dict[str, Any]] = []

        def add_result(
            label: str,
            mode: str,
            path: list[str] | None,
            cost: float,
            sec: float,
            timed_out: bool,
        ) -> None:
            est_time = cls._estimate_time(G, path, disaster_events)
            safety = cls._safety_score(G, path, disaster_events)
            cong = cls._compute_congestion(G, path)
            dist_km = cls._path_distance(G, path)
            results.append(
                {
                    "algorithm": label,
                    "algorithm_used": f"{label} ({mode})",
                    "mode": mode,
                    "path": path,
                    "cost": cost,
                    "weighted_cost": cost,
                    "estimated_time_min": est_time,
                    "safety_score": safety,
                    "congestion_score": cong,
                    "distance_km": dist_km,
                    "compute_time_sec": sec,
                    "ran_in_ms": sec * 1000.0,
                    "timed_out": timed_out,
                }
            )

        # --- Candidate runs ---
        def run_dijkstra_bal():
            return dijkstra(w_bal, start, goal)

        out, dt, to = _timeout_run(run_dijkstra_bal, cls.TIMEOUT_SEC)
        if out and not to:
            path, cost = out
            add_result("Dijkstra", "balanced", path, cost, dt, False)
        else:
            add_result("Dijkstra", "balanced", None, float("inf"), dt, to)

        def run_astar_fast():
            return astar(w_fast, start, goal, euclidean_distance, pos)

        out, dt, to = _timeout_run(run_astar_fast, cls.TIMEOUT_SEC)
        if out and not to:
            path, cost = out
            add_result("A*", "fastest", path, cost, dt, False)
        else:
            add_result("A*", "fastest", None, float("inf"), dt, to)

        def run_astar_safe():
            return astar(w_safe, start, goal, euclidean_distance, pos)

        out, dt, to = _timeout_run(run_astar_safe, cls.TIMEOUT_SEC)
        if out and not to:
            path, cost = out
            add_result("A*", "safest", path, cost, dt, False)
        else:
            add_result("A*", "safest", None, float("inf"), dt, to)

        if disaster_pressure < 0.2:

            def run_bfs():
                p = bfs(unw, start, goal)
                c = float(len(p) - 1) if p else float("inf")
                return p, c

            out, dt, to = _timeout_run(run_bfs, cls.TIMEOUT_SEC)
            if out and not to:
                path, hops = out
                add_result("BFS", "unweighted", path, hops, dt, False)
            else:
                add_result("BFS", "unweighted", None, float("inf"), dt, to)

        if n < 50 or disaster_pressure > 0.6:

            def run_bidir_d():
                return bidirectional_dijkstra(w_bal, start, goal)

            out, dt, to = _timeout_run(run_bidir_d, cls.TIMEOUT_SEC)
            if out and not to:
                path, cost = out
                add_result("Bidirectional Dijkstra", "balanced", path, cost, dt, False)
            else:
                add_result("Bidirectional Dijkstra", "balanced", None, float("inf"), dt, to)

        if bridge_on_default or critical_on_path:

            def run_greedy():
                return greedy_best_first(w_fast, start, goal, euclidean_distance, pos)

            out, dt, to = _timeout_run(run_greedy, cls.TIMEOUT_SEC)
            if out and not to:
                path, cost = out
                add_result("Greedy Best-First", "fastest", path, cost, dt, False)
            else:
                add_result("Greedy Best-First", "fastest", None, float("inf"), dt, to)

        def run_ucs():
            return ucs(w_bal, start, goal)

        out, dt, to = _timeout_run(run_ucs, cls.TIMEOUT_SEC)
        if out and not to:
            path, cost = out
            add_result("UCS", "balanced", path, cost, dt, False)
        else:
            add_result("UCS", "balanced", None, float("inf"), dt, to)

        if disaster_pressure > 0.4:

            def run_dstar():
                d = DStarLite(w_bal, start, goal, pos)
                d.compute_shortest_path()
                pth = d.get_path()
                cst = d._cost if pth else float("inf")
                return d, pth, cst

            out, dt, to = _timeout_run(run_dstar, cls.TIMEOUT_SEC)
            if out and not to:
                ds, path, cost = out
                dstar_runtime.set_active_dstar(ds)
                add_result("D* Lite", "balanced", path, cost, dt, False)
            else:
                dstar_runtime.set_active_dstar(None)
                add_result("D* Lite", "balanced", None, float("inf"), dt, to)
        else:
            dstar_runtime.set_active_dstar(None)

        def run_aco():
            return ant_colony_optimization(w_bal, start, goal, pos)

        out, dt, to = _timeout_run(run_aco, cls.TIMEOUT_SEC)
        if out and not to:
            path, cost = out
            add_result("Ant Colony", "balanced", path, cost, dt, False)
        else:
            add_result("Ant Colony", "balanced", None, float("inf"), dt, to)

        # Filter valid
        valid = [r for r in results if r.get("path") and not r.get("timed_out")]
        if not valid:
            best_invalid = min(results, key=lambda x: x.get("compute_time_sec", 0))
            best_invalid = dict(best_invalid)
            best_invalid.setdefault("composite_score", float("inf"))
            best_invalid.setdefault(
                "why_selected",
                "No algorithm produced a feasible path within the time budget.",
            )
            return cls._assemble_return(
                best_invalid,
                [],
                results,
                disaster_pressure,
                graph_density,
                [],
                [],
                "low",
                default_path,
            )

        tts = [r["estimated_time_min"] for r in valid]
        risks = [1.0 - r["safety_score"] / 100.0 for r in valid]
        dists = [r["distance_km"] for r in valid]
        congs = [r["congestion_score"] for r in valid]

        nt = cls._normalize(tts)
        nr = cls._normalize(risks)
        nd = cls._normalize(dists)
        nc = cls._normalize(congs)

        scored: list[tuple[float, dict[str, Any]]] = []
        for r, a, b, c, d in zip(valid, nt, nr, nd, nc):
            comp = 0.35 * a + 0.30 * b + 0.20 * c + 0.15 * d
            rr = dict(r)
            rr["composite_score"] = comp
            scored.append((comp, rr))

        scored.sort(key=lambda x: x[0])
        recommended = scored[0][1]
        alts = [scored[i][1] for i in range(1, min(3, len(scored)))]

        crit_list = [n for n in (default_path or []) if compute_risk_score(n, disaster_events) > 0.7]
        br_list = [n for n in (default_path or []) if G.nodes[n].get("node_type") == "bridge"]

        conf = "high"
        if disaster_pressure > 0.5 or len(valid) < 3:
            conf = "medium"
        if disaster_pressure > 0.75 or not recommended.get("path"):
            conf = "low"

        scenario = {
            "disaster_pressure": disaster_pressure,
            "graph_density": graph_density,
            "critical_on_path": critical_on_path,
            "bridge_on_default": bridge_on_default,
        }
        why = cls._get_why_selected(
            str(recommended.get("algorithm", "")),
            str(recommended.get("mode", "")),
            {
                "disaster_pressure": disaster_pressure,
                "critical_on_path": critical_on_path,
            },
        )
        recommended["why_selected"] = why

        return {
            "recommended": recommended,
            "alternatives": alts[:2],
            "all_results": results,
            "scenario_analysis": {
                "disaster_pressure": disaster_pressure,
                "graph_density": graph_density,
                "critical_nodes_on_path": crit_list,
                "bridge_nodes_on_path": br_list,
                "recommendation_confidence": conf,
            },
        }

    @staticmethod
    def _estimate_time(G: nx.Graph, path: list[str] | None, events: list[dict]) -> float:
        if not path or len(path) < 2:
            return float("inf")
        t = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            t += graph_engine.get_edge_weight(G, u, v, "fastest", active_events=events)
        return t

    @staticmethod
    def _safety_score(G: nx.Graph, path: list[str] | None, events: list[dict]) -> float:
        if not path:
            return 0.0
        from utils import metrics

        return metrics.safety_score_path(G, path, active_events=events)

    @staticmethod
    def _path_distance(G: nx.Graph, path: list[str] | None) -> float:
        if not path or len(path) < 2:
            return 0.0
        d = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if G.has_edge(u, v):
                d += float(G.edges[u, v].get("distance_km", 0))
        return d

    @staticmethod
    def _assemble_return(
        rec: dict[str, Any],
        alts: list[dict],
        all_res: list[dict],
        dp: float,
        gd: float,
        crit: list[str],
        br: list[str],
        conf: str,
        default_path: list[str] | None,
    ) -> dict[str, Any]:
        _ = default_path
        rec.setdefault("why_selected", "No viable path — all candidates failed or timed out.")
        return {
            "recommended": rec,
            "alternatives": alts,
            "all_results": all_res,
            "scenario_analysis": {
                "disaster_pressure": dp,
                "graph_density": gd,
                "critical_nodes_on_path": crit,
                "bridge_nodes_on_path": br,
                "recommendation_confidence": conf,
            },
        }
