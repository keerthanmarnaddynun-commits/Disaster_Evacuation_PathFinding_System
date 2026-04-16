import heapq
import math


def euclidean_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def astar(graph, start, goal, heuristic, positions) -> tuple[list[str] | None, float]:
    if start == goal:
        return [start], 0.0

    def h(n: str) -> float:
        pa = positions.get(n)
        pb = positions.get(goal)
        if pa is None or pb is None:
            return 0.0
        return float(heuristic(pa, pb))

    g_score: dict[str, float] = {start: 0.0}
    parent: dict[str, str | None] = {start: None}
    pq: list[tuple[float, float, str]] = [(h(start), 0.0, start)]
    closed: set[str] = set()

    while pq:
        _, g, node = heapq.heappop(pq)
        if node in closed:
            continue
        closed.add(node)
        if node == goal:
            path: list[str] = []
            cur: str | None = goal
            while cur is not None:
                path.append(cur)
                cur = parent.get(cur)
            path.reverse()
            return path, float(g_score.get(goal, g))

        for nbr, w in graph.get(node, []):
            if nbr in closed:
                continue
            ng = g_score[node] + float(w)
            if ng < g_score.get(nbr, float("inf")):
                g_score[nbr] = ng
                parent[nbr] = node
                heapq.heappush(pq, (ng + h(nbr), ng, nbr))

    return None, float("inf")