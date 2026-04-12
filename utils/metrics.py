"""Path cost, time, and safety scoring."""

from __future__ import annotations

import math
from typing import Any

import networkx as nx

from core import graph_engine


def path_travel_time_minutes(
    G: nx.Graph,
    path: list[str],
    *,
    active_events: list[dict] | None = None,
) -> float:
    """Sum of fastest-mode edge weights along path (interpreted as minutes)."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        total += graph_engine.get_edge_weight(G, u, v, "fastest", active_events=active_events)
    return total


def path_weighted_cost(
    G: nx.Graph,
    path: list[str],
    mode: str,
    *,
    active_events: list[dict] | None = None,
) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        w = graph_engine.get_edge_weight(G, u, v, mode, active_events=active_events)
        if math.isinf(w):
            return float("inf")
        total += w
    return total


def safety_score_path(
    G: nx.Graph,
    path: list[str],
    *,
    active_events: list[dict] | None = None,
) -> float:
    """
    0 worst .. 100 best: inverse of risk exposure along path.
    """
    if not path:
        return 0.0
    from core.disaster_manager import compute_risk_score

    events = active_events or []
    risks = [compute_risk_score(n, events) for n in path]
    avg = sum(risks) / max(len(risks), 1)
    return max(0.0, min(100.0, 100.0 * (1.0 - avg)))
