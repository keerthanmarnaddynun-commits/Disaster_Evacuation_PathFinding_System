"""
A* (A-Star) Algorithm - Pathfinding Algorithm
DAA Project

Time Complexity:  O(E log V)  with a good heuristic (E = edges explored)
Space Complexity: O(V)
Guarantee:        Optimal shortest path when heuristic is admissible (never overestimates)

A* improves over Dijkstra by using a heuristic h(n) to guide the search
toward the goal, reducing the number of nodes explored.

f(n) = g(n) + h(n)
  g(n) = actual cost from start to n
  h(n) = estimated cost from n to goal (heuristic)
"""

import heapq
import math


# ── Heuristic Functions ───────────────────────────────────────────────────────

def manhattan_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Manhattan distance — for grids with 4-directional movement."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def euclidean_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Euclidean distance — for grids with diagonal movement."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def chebyshev_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Chebyshev distance — for 8-directional movement."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# ── A* on Weighted Graph (General) ───────────────────────────────────────────

def astar(
    graph: dict,
    start: str,
    goal: str,
    heuristic: callable,
    positions: dict,
) -> tuple[list[str] | None, float]:
    """
    Find the shortest path using A* on a general weighted graph.

    Args:
        graph:     Weighted adjacency list {node: [(neighbor, weight), ...]}
        start:     Starting node
        goal:      Target node
        heuristic: Function heuristic(node_pos, goal_pos) -> estimated cost
        positions: Node coordinates {node: (x, y)} used by the heuristic

    Returns:
        Tuple of (path as list of nodes, total cost).
        Path is None and cost is infinity if no path exists.
    """
    goal_pos = positions[goal]

    # Min-heap: (f_score, g_score, current_node, path)
    heap = [(heuristic(positions[start], goal_pos), 0, start, [start])]

    # Best known g-score (actual cost from start) for each node
    best_g: dict[str, float] = {start: 0}

    while heap:
        f, g, node, path = heapq.heappop(heap)

        if node == goal:
            return path, g

        # Skip if a cheaper route to this node was already processed
        if g > best_g.get(node, float("inf")):
            continue

        for neighbor, weight in graph.get(node, []):
            new_g = g + weight

            if new_g < best_g.get(neighbor, float("inf")):
                best_g[neighbor] = new_g
                h = heuristic(positions[neighbor], goal_pos)
                heapq.heappush(heap, (new_g + h, new_g, neighbor, path + [neighbor]))

    return None, float("inf")


# ── A* on a 2-D Grid ─────────────────────────────────────────────────────────

def astar_grid(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    allow_diagonal: bool = False,
) -> list[tuple[int, int]] | None:
    """
    Find the shortest path on a 2-D grid using A*.

    Args:
        grid:           2-D list where 0 = passable, 1 = wall
        start:          (row, col) of start cell
        goal:           (row, col) of goal cell
        allow_diagonal: Whether diagonal moves are permitted

    Returns:
        List of (row, col) tuples representing the path, or None.
    """
    rows, cols = len(grid), len(grid[0])

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if allow_diagonal:
        directions += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    heuristic = chebyshev_distance if allow_diagonal else manhattan_distance

    heap = [(heuristic(start, goal), 0, start, [start])]
    best_g: dict[tuple, float] = {start: 0}

    while heap:
        f, g, cell, path = heapq.heappop(heap)

        if cell == goal:
            return path

        if g > best_g.get(cell, float("inf")):
            continue

        r, c = cell
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0:
                move_cost = math.sqrt(2) if (dr != 0 and dc != 0) else 1
                new_g = g + move_cost
                neighbor = (nr, nc)

                if new_g < best_g.get(neighbor, float("inf")):
                    best_g[neighbor] = new_g
                    h = heuristic(neighbor, goal)
                    heapq.heappush(heap, (new_g + h, new_g, neighbor, path + [neighbor]))

    return None


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Example 1: General weighted graph ────────────────────────────────────
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

    # 2-D coordinates used by the heuristic
    positions = {
        "A": (0, 0), "B": (1, 1), "C": (0, 2),
        "D": (2, 2), "E": (2, 3), "F": (1, 4),
        "G": (3, 3), "H": (3, 4),
    }

    start, goal = "A", "H"
    print("=== A* on Weighted Graph ===")
    path, cost = astar(graph, start, goal, euclidean_distance, positions)
    if path:
        print(f"  Path : {' → '.join(path)}")
        print(f"  Cost : {cost}")
    else:
        print("  No path found.")

    # ── Example 2: Grid ───────────────────────────────────────────────────────
    grid = [
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 1, 0],
        [0, 1, 0, 0, 0],
        [0, 0, 0, 1, 0],
    ]

    start_cell, goal_cell = (0, 0), (4, 4)
    print("\n=== A* on 2-D Grid ===")
    print("Grid (0=open, 1=wall):")
    for row in grid:
        print(" ", row)

    path_grid = astar_grid(grid, start_cell, goal_cell)
    if path_grid:
        print(f"\n  Path  : {path_grid}")
        print(f"  Steps : {len(path_grid) - 1}")
    else:
        print("\n  No path found.")