"""Rescue units, dispatch, occupancy, reporting."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import networkx as nx
import pandas as pd

from algorithms.Dijkstra import dijkstra

from core import data_loader, graph_engine


def load_units() -> list[dict[str, Any]]:
    return data_loader.read_rescue_units()


def save_units(units: list[dict[str, Any]]) -> None:
    data_loader.write_rescue_units(units)


def assign_unit(
    G: nx.Graph,
    unit: dict[str, Any],
    zone_id: str,
    *,
    algorithm_used: str = "dijkstra",
    route_path: list[str] | None = None,
    total_cost: float = 0.0,
    people: int = 0,
    status: str = "deployed",
) -> None:
    """Dispatch unit to zone, append rescue log, set unit status."""
    units = load_units()
    for u in units:
        if u.get("unit_id") == unit.get("unit_id"):
            u["status"] = status
            if route_path:
                u["location_node"] = route_path[-1]
            break
    save_units(units)

    row = {
        "log_id": data_loader.next_log_id(),
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "zone": zone_id,
        "algorithm_used": algorithm_used,
        "path": ",".join(route_path) if route_path else "",
        "total_cost": f"{total_cost:.4f}",
        "people_evacuated": str(people),
        "rescue_unit": unit.get("unit_id", ""),
        "status": "completed" if status == "deployed" else status,
    }
    data_loader.append_rescue_log_row(row)


def get_optimal_dispatch(
    G: nx.Graph,
    units: list[dict[str, Any]],
    zone: dict[str, Any],
    *,
    mode: str = "fastest",
) -> dict[str, Any] | None:
    """Pick nearest available unit to any node in zone using Dijkstra."""
    events = data_loader.read_disaster_events()
    wadj = graph_engine.to_weighted_adjacency(G, mode, active_events=events)
    zone_nodes = set(zone.get("nodes", []))
    candidates = [u for u in units if u.get("status") == "available"]
    if not candidates or not zone_nodes:
        return None

    best_u: dict[str, Any] | None = None
    best_cost = float("inf")

    for unit in candidates:
        loc = unit.get("location_node")
        if loc not in G:
            continue
        for target in zone_nodes:
            if target not in G:
                continue
            t0 = time.perf_counter()
            path, cost = dijkstra(wadj, loc, target)
            _ = time.perf_counter() - t0
            if path and cost < best_cost:
                best_cost = cost
                best_u = unit

    return best_u


def update_occupancy(safe_zone_id: str, count: int) -> None:
    zones = data_loader.read_safe_zones()
    for z in zones:
        if z.get("id") == safe_zone_id:
            cur = int(z.get("current_occupancy", 0))
            cap = int(z.get("capacity", 0))
            z["current_occupancy"] = min(cap, max(0, cur + count))
            break
    data_loader.write_safe_zones(zones)


def generate_rescue_report() -> pd.DataFrame:
    rows = data_loader.read_rescue_log_rows()
    if not rows:
        return pd.DataFrame(
            columns=[
                "log_id",
                "timestamp",
                "zone",
                "algorithm_used",
                "path",
                "total_cost",
                "people_evacuated",
                "rescue_unit",
                "status",
            ]
        )
    return pd.DataFrame(rows)
