"""
BFS (Breadth-First Search) - Pathfinding Algorithm
DAA Project

Time Complexity:  O(V + E)  — V = vertices, E = edges
Space Complexity: O(V)
Guarantee:        Shortest path in an unweighted graph
"""

from collections import deque


def bfs(graph: dict, start: str, goal: str) -> list[str] | None:
    """
    Find the shortest path from start to goal using BFS.

    Args:
        graph: Adjacency list {node: [neighbors]}
        start: Starting node
        goal:  Target node

    Returns:
        List of nodes representing the path, or None if no path exists.
    """
    if start == goal:
        return [start]

    # Queue stores (current_node, path_so_far)
    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        node, path = queue.popleft()

        for neighbor in graph.get(node, []):
            if neighbor == goal:
                return path + [neighbor]

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None  # No path found


def bfs_all_paths(graph: dict, start: str, goal: str) -> list[list[str]]:
    """
    Find ALL shortest paths from start to goal using BFS.

    Returns:
        List of all shortest paths.
    """
    if start == goal:
        return [[start]]

    queue = deque([(start, [start])])
    visited: dict[str, int] = {start: 0}  # node -> depth at which first visited
    shortest_len = float("inf")
    results = []

    while queue:
        node, path = queue.popleft()

        if len(path) > shortest_len:
            break

        for neighbor in graph.get(node, []):
            new_path = path + [neighbor]

            if neighbor == goal:
                shortest_len = len(new_path)
                results.append(new_path)
            elif neighbor not in visited or visited[neighbor] == len(new_path) - 1:
                visited[neighbor] = len(new_path) - 1
                queue.append((neighbor, new_path))

    return results


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    graph = {
        "A": ["B", "C"],
        "B": ["A", "D", "E"],
        "C": ["A", "F"],
        "D": ["B", "G"],
        "E": ["B", "F", "G"],
        "F": ["C", "E", "H"],
        "G": ["D", "E", "H"],
        "H": ["F", "G"],
    }

    start, goal = "A", "H"

    print(f"Graph: {graph}")
    print(f"\nBFS shortest path from '{start}' to '{goal}':")
    path = bfs(graph, start, goal)
    if path:
        print(f"  Path   : {' → '.join(path)}")
        print(f"  Length : {len(path) - 1} edges")
    else:
        print("  No path found.")

    print(f"\nAll shortest paths from '{start}' to '{goal}':")
    all_paths = bfs_all_paths(graph, start, goal)
    for i, p in enumerate(all_paths, 1):
        print(f"  [{i}] {' → '.join(p)}")