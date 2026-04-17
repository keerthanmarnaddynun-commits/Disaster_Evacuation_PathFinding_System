def dfs(graph: dict, start: str, goal: str) -> list[str] | None:
    if start == goal:
        return [start]

    stack: list[tuple[str, list[str]]] = [(start, [start])]
    visited: set[str] = {start}

    while stack:
        node, path = stack.pop()
        for nbr in graph.get(node, []):
            if nbr == goal:
                return path + [nbr]
            if nbr in visited:
                continue
            visited.add(nbr)
            stack.append((nbr, path + [nbr]))

    return None