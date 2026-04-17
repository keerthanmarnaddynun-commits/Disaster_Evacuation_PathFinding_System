import heapq

def ucs(graph: dict, start: str, goal: str) -> tuple[list[str] | None, float]:
    if start == goal:
        return [start], 0.0

    frontier: list[tuple[float, str, list[str]]] = [(0.0, start, [start])]
    explored: set[str] = set()

    while frontier:
        cost, node, path = heapq.heappop(frontier)
        if node in explored:
            continue
        explored.add(node)
        if node == goal:
            return path, float(cost)

        for nbr, w in graph.get(node, []):
            if nbr in explored:
                continue
            heapq.heappush(frontier, (cost + float(w), nbr, path + [nbr]))

    return None, float("inf")
