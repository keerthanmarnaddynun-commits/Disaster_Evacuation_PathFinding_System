"""
DFS (Depth-First Search) - Pathfinding Algorithm
DAA Project

Time Complexity:  O(V + E)  — V = vertices, E = edges
Space Complexity: O(V)      — recursion / explicit stack depth
Guarantee:        Finds A path, not necessarily the shortest
"""


def dfs(graph: dict, start: str, goal: str) -> list[str] | None:
    """
    Find a path from start to goal using iterative DFS.

    Args:
        graph: Adjacency list {node: [neighbors]}
        start: Starting node
        goal:  Target node

    Returns:
        List of nodes representing the path, or None if no path exists.
    """
    if start == goal:
        return [start]

    # Stack stores (current_node, path_so_far)
    stack = [(start, [start])]
    visited = {start}

    while stack:
        node, path = stack.pop()

        for neighbor in graph.get(node, []):
            if neighbor == goal:
                return path + [neighbor]

            if neighbor not in visited:
                visited.add(neighbor)
                stack.append((neighbor, path + [neighbor]))

    return None  # No path found


def dfs_recursive(
    graph: dict,
    current: str,
    goal: str,
    visited: set | None = None,
    path: list | None = None,
) -> list[str] | None:
    """
    Find a path from current to goal using recursive DFS.

    Args:
        graph:   Adjacency list {node: [neighbors]}
        current: Current node being explored
        goal:    Target node
        visited: Set of already-visited nodes (managed internally)
        path:    Current path (managed internally)

    Returns:
        List of nodes representing the path, or None if no path exists.
    """
    if visited is None:
        visited = set()
    if path is None:
        path = []

    visited.add(current)
    path = path + [current]

    if current == goal:
        return path

    for neighbor in graph.get(current, []):
        if neighbor not in visited:
            result = dfs_recursive(graph, neighbor, goal, visited, path)
            if result is not None:
                return result

    return None


def dfs_all_paths(
    graph: dict,
    current: str,
    goal: str,
    visited: set | None = None,
    path: list | None = None,
) -> list[list[str]]:
    """
    Find ALL paths from start to goal using DFS (no revisiting nodes).

    Returns:
        List of all valid paths.
    """
    if visited is None:
        visited = set()
    if path is None:
        path = []

    visited = visited | {current}  # copy to allow backtracking
    path = path + [current]

    if current == goal:
        return [path]

    all_paths = []
    for neighbor in graph.get(current, []):
        if neighbor not in visited:
            results = dfs_all_paths(graph, neighbor, goal, visited, path)
            all_paths.extend(results)

    return all_paths


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

    print(f"\nDFS path (iterative) from '{start}' to '{goal}':")
    path = dfs(graph, start, goal)
    if path:
        print(f"  Path   : {' → '.join(path)}")
        print(f"  Length : {len(path) - 1} edges")
    else:
        print("  No path found.")

    print(f"\nDFS path (recursive) from '{start}' to '{goal}':")
    path_r = dfs_recursive(graph, start, goal)
    if path_r:
        print(f"  Path   : {' → '.join(path_r)}")
        print(f"  Length : {len(path_r) - 1} edges")
    else:
        print("  No path found.")

    print(f"\nAll DFS paths from '{start}' to '{goal}':")
    all_paths = dfs_all_paths(graph, start, goal)
    for i, p in enumerate(all_paths, 1):
        print(f"  [{i}] {' → '.join(p)}  (length {len(p) - 1})")