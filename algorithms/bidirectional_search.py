"""
Bidirectional BFS and Bidirectional Dijkstra.
"""

from __future__ import annotations

import heapq


def _reverse_graph_weighted(graph: dict[str, list[tuple[str, float]]]) -> dict[str, list[tuple[str, float]]]:
    rev: dict[str, list[tuple[str, float]]] = {}
    for u, nbs in graph.items():
        for v, w in nbs:
            rev.setdefault(v, []).append((u, w))
    return rev


def bidirectional_bfs(graph: dict[str, list[str]], start: str, goal: str) -> list[str] | None:
    """Unweighted adjacency: {node: [neighbors]}."""
    if start == goal:
        return [start]

    rev: dict[str, list[str]] = {}
    for u, nbs in graph.items():
        for v in nbs:
            rev.setdefault(v, []).append(u)

    pred_f: dict[str, str | None] = {start: None}
    pred_b: dict[str, str | None] = {goal: None}
    front_f = {start}
    front_b = {goal}
    meeting: str | None = None

    while front_f and front_b and meeting is None:
        if len(front_f) <= len(front_b):
            nxt: set[str] = set()
            for x in list(front_f):
                for y in graph.get(x, []):
                    if y in pred_b:
                        meeting = y
                        pred_f[y] = x
                        break
                    if y not in pred_f:
                        pred_f[y] = x
                        nxt.add(y)
                if meeting:
                    break
            front_f = nxt
        else:
            nxt = set()
            for x in list(front_b):
                for y in rev.get(x, []):
                    if y in pred_f:
                        meeting = y
                        pred_b[y] = x
                        break
                    if y not in pred_b:
                        pred_b[y] = x
                        nxt.add(y)
                if meeting:
                    break
            front_b = nxt

    if meeting is None:
        return None

    left: list[str] = []
    cur: str | None = meeting
    while cur is not None:
        left.append(cur)
        cur = pred_f[cur]
    left.reverse()

    right: list[str] = []
    cur = pred_b[meeting]
    while cur is not None:
        right.append(cur)
        cur = pred_b[cur]

    return left + right


def bidirectional_dijkstra(
    graph: dict[str, list[tuple[str, float]]],
    start: str,
    goal: str,
) -> tuple[list[str] | None, float]:
    """Two Dijkstra waves; stitch at minimum combined distance."""
    if start == goal:
        return [start], 0.0

    rev = _reverse_graph_weighted(graph)
    inf = float("inf")
    dist_f: dict[str, float] = {start: 0.0}
    dist_b: dict[str, float] = {goal: 0.0}
    pred_f: dict[str, str | None] = {start: None}
    pred_b: dict[str, str | None] = {goal: None}

    pq_f: list[tuple[float, str]] = [(0.0, start)]
    pq_b: list[tuple[float, str]] = [(0.0, goal)]
    best_mu = inf
    best_meet: str | None = None

    while pq_f or pq_b:
        if pq_f:
            df, u = heapq.heappop(pq_f)
            if df > dist_f.get(u, inf):
                continue
            for v, w in graph.get(u, []):
                nd = df + w
                if nd < dist_f.get(v, inf):
                    dist_f[v] = nd
                    pred_f[v] = u
                    heapq.heappush(pq_f, (nd, v))
                    if v in dist_b:
                        mu = nd + dist_b[v]
                        if mu < best_mu:
                            best_mu = mu
                            best_meet = v

        if pq_b:
            db, u = heapq.heappop(pq_b)
            if db > dist_b.get(u, inf):
                continue
            for v, w in rev.get(u, []):
                nd = db + w
                if nd < dist_b.get(v, inf):
                    dist_b[v] = nd
                    pred_b[v] = u
                    heapq.heappush(pq_b, (nd, v))
                    if v in dist_f:
                        mu = dist_f[v] + nd
                        if mu < best_mu:
                            best_mu = mu
                            best_meet = v

        top_f = pq_f[0][0] if pq_f else inf
        top_b = pq_b[0][0] if pq_b else inf
        if best_meet is not None and top_f + top_b >= best_mu:
            break

    if best_meet is None or best_mu == inf:
        return None, inf

    left: list[str] = []
    cur: str | None = best_meet
    while cur is not None:
        left.append(cur)
        cur = pred_f[cur]
    left.reverse()

    right: list[str] = []
    cur = pred_b[best_meet]
    while cur is not None:
        right.append(cur)
        cur = pred_b[cur]

    return left + right, best_mu
