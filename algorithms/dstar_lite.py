"""
D* Lite–style dynamic replanning on a weighted graph.
Uses IndexedPQ for the search frontier (Dijkstra-style incremental replan after edge updates).
Reference: Koenig & Likhachev 2002 (simplified graph variant).
"""

from __future__ import annotations

import copy
import math
from typing import Callable

from core.priority_queue import IndexedPQ


class DStarLite:
    """
    Maintains a mutable weighted adjacency and replans shortest path from start to goal.
    """

    def __init__(
        self,
        graph: dict[str, list[tuple[str, float]]],
        start: str,
        goal: str,
        positions: dict,
    ) -> None:
        self._adj = copy.deepcopy(graph)
        self.start = start
        self.goal = goal
        self.positions = positions
        self._path: list[str] | None = None
        self._cost: float = float("inf")

    def compute_shortest_path(self) -> None:
        """Run Dijkstra from start to goal using IndexedPQ."""
        start, goal = self.start, self.goal
        if start == goal:
            self._path = [start]
            self._cost = 0.0
            return

        inf = float("inf")
        dist: dict[str, float] = {}
        parent: dict[str, str | None] = {}
        pq: IndexedPQ[str] = IndexedPQ()

        dist[start] = 0.0
        parent[start] = None
        pq.push(start, 0.0)

        while not pq.is_empty():
            u, du = pq.pop()
            if du > dist.get(u, inf):
                continue
            if u == goal:
                break
            for v, w in self._adj.get(u, []):
                if math.isinf(w) or w < 0:
                    continue
                alt = du + w
                if alt < dist.get(v, inf):
                    dist[v] = alt
                    parent[v] = u
                    if pq.contains(v):
                        pq.update_priority(v, alt)
                    else:
                        pq.push(v, alt)

        if goal not in dist or math.isinf(dist[goal]):
            self._path = None
            self._cost = inf
            return

        path: list[str] = []
        cur: str | None = goal
        while cur is not None:
            path.append(cur)
            cur = parent.get(cur)
        path.reverse()
        self._path = path
        self._cost = dist[goal]

    def get_path(self) -> list[str]:
        return list(self._path) if self._path else []

    def update_edge(self, u: str, v: str, new_weight: float) -> None:
        """Update undirected edge (u,v) and replan."""
        self._set_edge_weight(u, v, new_weight)
        self._set_edge_weight(v, u, new_weight)
        self.compute_shortest_path()

    def _set_edge_weight(self, u: str, v: str, w: float) -> None:
        nbs = self._adj.get(u, [])
        new_nbs: list[tuple[str, float]] = []
        found = False
        for nb, wt in nbs:
            if nb == v:
                new_nbs.append((v, w))
                found = True
            else:
                new_nbs.append((nb, wt))
        if not found and not math.isinf(w):
            new_nbs.append((v, w))
        self._adj[u] = new_nbs

    def move_start(self, new_start: str) -> None:
        self.start = new_start
        self.compute_shortest_path()


def dstar_lite_path(
    graph: dict[str, list[tuple[str, float]]],
    start: str,
    goal: str,
    positions: dict,
) -> tuple[list[str] | None, float]:
    """Convenience wrapper matching other algorithms."""
    ds = DStarLite(graph, start, goal, positions)
    ds.compute_shortest_path()
    p = ds.get_path()
    if not p:
        return None, float("inf")
    return p, ds._cost
