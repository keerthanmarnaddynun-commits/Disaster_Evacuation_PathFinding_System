"""
Ant Colony Optimization — probabilistic path construction with pheromone trails.
"""

from __future__ import annotations

import math
import random
from typing import Callable

import numpy as np


def ant_colony_optimization(
    graph: dict[str, list[tuple[str, float]]],
    start: str,
    goal: str,
    positions: dict,
    n_ants: int = 20,
    n_iterations: int = 50,
    alpha: float = 1.0,
    beta: float = 2.0,
    evaporation: float = 0.5,
    Q: float = 100.0,
    heuristic: Callable | None = None,
) -> tuple[list[str] | None, float]:
    """
    Returns best path found and its cost (sum of edge weights).
    """
    if start == goal:
        return [start], 0.0

    nodes = sorted(graph.keys())
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    if start not in idx or goal not in idx:
        return None, float("inf")

    edges: dict[tuple[int, int], float] = {}
    for u, nbs in graph.items():
        iu = idx.get(u)
        if iu is None:
            continue
        for v, w in nbs:
            iv = idx.get(v)
            if iv is None or math.isinf(w):
                continue
            a, b = (iu, iv) if iu <= iv else (iv, iu)
            edges[(a, b)] = min(edges.get((a, b), w), w)

    tau = np.ones((n, n), dtype=float) * 0.1
    goal_pos = positions[goal]
    if heuristic is None:

        def h(pu, pg):
            return math.hypot(pu[0] - pg[0], pu[1] - pg[1]) + 1e-6

    else:
        h = heuristic

    best_path: list[str] | None = None
    best_cost = float("inf")
    rng = random.Random(42)

    for _ in range(n_iterations):
        for _ant in range(n_ants):
            path_idx = [idx[start]]
            visited = {start}
            cur = start
            while cur != goal and len(path_idx) < n * 3:
                neighbors: list[tuple[str, float]] = []
                for v, w in graph.get(cur, []):
                    if v not in visited and not math.isinf(w):
                        neighbors.append((v, w))
                if not neighbors:
                    break
                probs: list[float] = []
                for v, w in neighbors:
                    iu, iv = idx[cur], idx[v]
                    a, b = (iu, iv) if iu <= iv else (iv, iu)
                    etau = tau[a, b] ** alpha
                    heur = (Q / (w + 1e-6)) ** beta * h(positions[v], goal_pos) ** beta
                    probs.append(etau * heur)
                s = sum(probs)
                if s <= 0:
                    break
                r = rng.random() * s
                acc = 0.0
                nxt = neighbors[0][0]
                for (v, _), p in zip(neighbors, probs):
                    acc += p
                    if acc >= r:
                        nxt = v
                        break
                path_idx.append(idx[nxt])
                visited.add(nxt)
                cur = nxt

            if cur != goal:
                continue

            path_nodes = [nodes[i] for i in path_idx]
            cost = 0.0
            ok = True
            for i in range(len(path_nodes) - 1):
                u, v = path_nodes[i], path_nodes[i + 1]
                w = _get_w(graph, u, v)
                if math.isinf(w):
                    ok = False
                    break
                cost += w
            if not ok:
                continue
            if cost < best_cost:
                best_cost = cost
                best_path = path_nodes

            delta = Q / (cost + 1e-6)
            for i in range(len(path_idx) - 1):
                a, b = path_idx[i], path_idx[i + 1]
                aa, bb = (a, b) if a <= b else (b, a)
                tau[aa, bb] += delta

        tau *= 1.0 - evaporation
        tau = np.clip(tau, 1e-6, 1e6)

    if best_path is None:
        return None, float("inf")
    return best_path, best_cost


def _get_w(graph: dict[str, list[tuple[str, float]]], u: str, v: str) -> float:
    for nb, w in graph.get(u, []):
        if nb == v:
            return w
    return float("inf")
