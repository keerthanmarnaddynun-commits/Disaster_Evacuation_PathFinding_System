"""
Dijkstra's Algorithm - Pathfinding Algorithm
DAA Project

Time Complexity:  O((V + E) log V)  with a min-heap priority queue
Space Complexity: O(V)
Guarantee:        Shortest path in a weighted graph with non-negative weights
"""

import heapq


def dijkstra(graph: dict, start: str, goal: str) -> tuple[list[str] | None, float]:
    """
    Find the shortest weighted path from start to goal using Dijkstra's algorithm.

    Args:
        graph: Weighted adjacency list {node: [(neighbor, weight), ...]}
        start: Starting node
        goal:  Target node

    Returns:
        Tuple of (path as list of nodes, total cost).
        Path is None and cost is infinity if no path exists.
    """
    # Min-heap: (cost, current_node, path_so_far)
    heap = [(0, start, [start])]

    # Best known cost to reach each node
    best_cost: dict[str, float] = {start: 0}

    while heap:
        cost, node, path = heapq.heappop(heap)

        # If we already found a cheaper route to this node, skip
        if cost > best_cost.get(node, float("inf")):
            continue

        if node == goal:
            return path, cost

        for neighbor, weight in graph.get(node, []):
            new_cost = cost + weight

            if new_cost < best_cost.get(neighbor, float("inf")):
                best_cost[neighbor] = new_cost
                heapq.heappush(heap, (new_cost, neighbor, path + [neighbor]))

    return None, float("inf")


def dijkstra_all_distances(graph: dict, start: str) -> dict[str, float]:
    """
    Compute the shortest distance from start to ALL reachable nodes.

    Args:
        graph: Weighted adjacency list {node: [(neighbor, weight), ...]}
        start: Source node

    Returns:
        Dictionary {node: shortest_distance_from_start}
    """
    heap = [(0, start)]
    dist: dict[str, float] = {start: 0}

    while heap:
        cost, node = heapq.heappop(heap)

        if cost > dist.get(node, float("inf")):
            continue

        for neighbor, weight in graph.get(node, []):
            new_cost = cost + weight
            if new_cost < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_cost
                heapq.heappush(heap, (new_cost, neighbor))

    return dist


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Weighted graph: {node: [(neighbor, weight), ...]}
    graph = {
        "A": [("B", 1), ("C", 4)],
        "B": [("A", 1), ("D", 2), ("E", 5)],
        "C": [("A", 4), ("F", 3)],
        "D": [("B", 2), ("G", 3)],
        "E": [("B", 5), ("F", 1), ("G", 2)],
        "F": [("C", 3), ("E", 1), ("H", 4)],
        "G": [("D", 3), ("E", 2), ("H", 1)],
        "H": [("F", 4), ("G", 1)],
    }

    start, goal = "A", "H"

    print(f"Weighted Graph: {graph}")

    print(f"\nDijkstra shortest path from '{start}' to '{goal}':")
    path, cost = dijkstra(graph, start, goal)
    if path:
        print(f"  Path  : {' → '.join(path)}")
        print(f"  Cost  : {cost}")
    else:
        print("  No path found.")

    print(f"\nAll shortest distances from '{start}':")
    distances = dijkstra_all_distances(graph, start)
    for node, dist in sorted(distances.items()):
        print(f"  {start} → {node} : {dist}")