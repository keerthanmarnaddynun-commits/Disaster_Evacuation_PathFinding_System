"""
UCS (Uniform Cost Search) — Dijkstra-equivalent with explicit frontier/explored.
Time: O((V+E) log V), Space: O(V)
Optimal: Yes (non-negative weights)
"""

from __future__ import annotations

import math

from core.priority_queue import MinHeapPQ


def ucs(graph: dict[str, list[tuple[str, float]]], start: str, goal: str) -> tuple[list[str] | None, float]:
    """
    Weighted adjacency list {node: [(neighbor, weight), ...]}.
    Returns (path, total_cost) or (None, inf).
    """
    if start == goal:
        return [start], 0.0

    pq: MinHeapPQ[tuple[str, list[str]]] = MinHeapPQ()
    pq.push(0.0, (start, [start]))
    best_cost: dict[str, float] = {start: 0.0}

    while not pq.is_empty():
        cost, (node, path) = pq.pop()
        if cost > best_cost.get(node, float("inf")):
            continue
        if node == goal:
            return path, cost

        for neighbor, w in graph.get(node, []):
            if w < 0 or math.isinf(w):
                continue
            new_cost = cost + w
            if new_cost < best_cost.get(neighbor, float("inf")):
                best_cost[neighbor] = new_cost
                pq.push(new_cost, (neighbor, path + [neighbor]))

    return None, float("inf")
