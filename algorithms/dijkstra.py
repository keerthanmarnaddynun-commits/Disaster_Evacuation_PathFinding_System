import heapq
import math


def dijkstra(graph: dict, start: str, goal: str) -> tuple[list[str] | None, float]:
    if start == goal:
        return [start], 0.0

    dist: dict[str, float] = {start: 0.0}
    parent: dict[str, str | None] = {start: None}
    pq: list[tuple[float, str]] = [(0.0, start)]

    while pq:
        d, node = heapq.heappop(pq)
        if d != dist.get(node, math.inf):
            continue
        if node == goal:
            # reconstruct
            path: list[str] = []
            cur: str | None = goal
            while cur is not None:
                path.append(cur)
                cur = parent.get(cur)
            path.reverse()
            return path, float(d)

        for nbr, w in graph.get(node, []):
            nd = d + float(w)
            if nd < dist.get(nbr, math.inf):
                dist[nbr] = nd
                parent[nbr] = node
                heapq.heappush(pq, (nd, nbr))

    return None, float("inf")


def dijkstra_all_distances(graph: dict, start: str) -> dict[str, float]:
    dist: dict[str, float] = {start: 0.0}
    pq: list[tuple[float, str]] = [(0.0, start)]

    while pq:
        d, node = heapq.heappop(pq)
        if d != dist.get(node, math.inf):
            continue
        for nbr, w in graph.get(node, []):
            nd = d + float(w)
            if nd < dist.get(nbr, math.inf):
                dist[nbr] = nd
                heapq.heappush(pq, (nd, nbr))

    return dist