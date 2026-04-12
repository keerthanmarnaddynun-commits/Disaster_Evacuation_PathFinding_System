"""Global hook so disaster_manager can notify the active D* Lite planner of edge updates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

_active_planner: Any = None


def set_active_dstar(planner: Any | None) -> None:
    """AlgorithmSelector registers the DStarLite instance used for the current session."""
    global _active_planner
    _active_planner = planner


def notify_edge_blocked(u: str, v: str) -> None:
    """Called from disaster_manager when a road is blocked."""
    if _active_planner is not None and hasattr(_active_planner, "update_edge"):
        _active_planner.update_edge(u, v, float("inf"))


def notify_edge_restored(u: str, v: str, weight: float) -> None:
    """Optional: unblock restores finite weight."""
    if _active_planner is not None and hasattr(_active_planner, "update_edge"):
        _active_planner.update_edge(u, v, weight)
