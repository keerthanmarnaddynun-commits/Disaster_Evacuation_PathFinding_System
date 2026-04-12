"""
Greedy Best-First Search — expands only toward goal (heuristic only).
Not optimal; fast approximation.
"""

from __future__ import annotations

from typing import Callable

from core.priority_queue import MinHeapPQ


def greedy_best_first(
    graph: dict[str, list[tuple[str, float]]],
    start: str,
    goal: str,
    heuristic: Callable,
    positions: dict,
) -> tuple[list[str] | None, float]:
    """
    Min-heap on h(n) only; visited set prevents cycles.
    Cost returned is sum of edge weights along chosen path (for reporting).
    """
    if start == goal:
        return [start], 0.0

    goal_pos = positions[goal]
    pq: MinHeapPQ[tuple[str, list[str]]] = MinHeapPQ()
    h0 = heuristic(positions[start], goal_pos)
    pq.push(h0, (start, [start]))
    visited: set[str] = {start}

    while not pq.is_empty():
        _, (node, path) = pq.pop()
        if node == goal:
            total = 0.0
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                w = _edge_weight(graph, u, v)
                if w == float("inf"):
                    return None, float("inf")
                total += w
            return path, total

        for neighbor, _w in graph.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            hn = heuristic(positions[neighbor], goal_pos)
            pq.push(hn, (neighbor, path + [neighbor]))

    return None, float("inf")


def _edge_weight(graph: dict[str, list[tuple[str, float]]], u: str, v: str) -> float:
    for nb, w in graph.get(u, []):
        if nb == v:
            return w
    return float("inf")
