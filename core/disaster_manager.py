"""Block/unblock roads, spread disaster, risk scoring."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

import networkx as nx

from core import data_loader, dstar_runtime, graph_engine


def _norm_edge(u: str, v: str) -> tuple[str, str]:
    return (u, v) if u <= v else (v, u)


def _events_list() -> list[dict]:
    return data_loader.read_disaster_events()


def _write_events(events: list[dict]) -> None:
    data_loader.write_disaster_events(events)


def collect_blocked_edges(events: list[dict] | None = None) -> set[tuple[str, str]]:
    """All blocked undirected edge keys from active events."""
    evs = events if events is not None else _events_list()
    blocked: set[tuple[str, str]] = set()
    for ev in evs:
        if not ev.get("active", True):
            continue
        for pair in ev.get("blocked_edges", []):
            if len(pair) >= 2:
                blocked.add(_norm_edge(str(pair[0]), str(pair[1])))
    return blocked


def apply_blocked_to_graph(G: nx.Graph, events: list[dict] | None = None) -> nx.Graph:
    """Return a copy of G with blocked edges removed."""
    H = G.copy()
    blocked = collect_blocked_edges(events)
    for u, v in blocked:
        if H.has_edge(u, v):
            H.remove_edge(u, v)
    return H


def block_road(G: nx.Graph, u: str, v: str, event_id: str | None = None) -> str:
    """Remove edge from G and append a synthetic block to disaster_events.json."""
    remove_edge = _norm_edge(u, v)
    if G.has_edge(u, v):
        G.remove_edge(u, v)

    events = _events_list()
    eid = event_id or f"EVT-MANUAL-{uuid.uuid4().hex[:8]}"
    found = False
    for ev in events:
        if ev.get("event_id") == eid:
            be = ev.setdefault("blocked_edges", [])
            if list(remove_edge) not in be and [remove_edge[0], remove_edge[1]] not in be:
                be.append([remove_edge[0], remove_edge[1]])
            found = True
            break
    if not found:
        events.append(
            {
                "event_id": eid,
                "type": "congestion",
                "severity": "medium",
                "affected_nodes": [],
                "blocked_edges": [[remove_edge[0], remove_edge[1]]],
                "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "active": True,
            }
        )
    _write_events(events)
    dstar_runtime.notify_edge_blocked(u, v)
    return eid


def unblock_road(G: nx.Graph, u: str, v: str) -> None:
    """Restore edge from city_graph seed and remove block from all events."""
    key = _norm_edge(u, v)
    raw = data_loader.read_city_graph()
    edge_data = None
    for e in raw.get("edges", []):
        eu, ev = e["source"], e["target"]
        if _norm_edge(eu, ev) == key:
            edge_data = e
            break
    if edge_data is None:
        return

    u0, v0 = edge_data["source"], edge_data["target"]
    attrs = {
        "distance_km": float(edge_data.get("distance_km", 1)),
        "base_travel_time_min": float(edge_data.get("base_travel_time_min", 1)),
        "capacity": float(edge_data.get("capacity", 500)),
        "road_name": edge_data.get("road_name", ""),
        "road_type": edge_data.get("road_type", "local"),
        "bidirectional": edge_data.get("bidirectional", True),
        "congestion_factor": float(edge_data.get("congestion_factor", 1.0)),
    }
    if not G.has_edge(u0, v0):
        G.add_edge(u0, v0, **attrs)

    events = _events_list()
    for ev in events:
        be = ev.get("blocked_edges", [])
        new_be = [p for p in be if _norm_edge(str(p[0]), str(p[1])) != key]
        ev["blocked_edges"] = new_be
    _write_events(events)

    evs = _events_list()
    if G.has_edge(u0, v0):
        w = graph_engine.get_edge_weight(G, u0, v0, "balanced", active_events=evs)
        dstar_runtime.notify_edge_restored(u0, v0, w)


def spread_disaster(
    G: nx.Graph,
    epicenter: str,
    radius_km: float,
    disaster_type: str,
    *,
    severity: str = "high",
) -> str:
    """Auto-block edges whose midpoint is within radius_km of epicenter coordinates."""
    if epicenter not in G:
        return ""

    ex = float(G.nodes[epicenter].get("x", 0))
    ey = float(G.nodes[epicenter].get("y", 0))

    blocked_pairs: list[list[str]] = []
    for u, v in list(G.edges()):
        x1 = float(G.nodes[u].get("x", 0))
        y1 = float(G.nodes[u].get("y", 0))
        x2 = float(G.nodes[v].get("x", 0))
        y2 = float(G.nodes[v].get("y", 0))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dist = math.hypot(mx - ex, my - ey)
        if dist <= radius_km:
            blocked_pairs.append([u, v])

    eid = f"EVT-SPREAD-{uuid.uuid4().hex[:8]}"
    events = _events_list()
    affected_nodes = [n for n in G.nodes() if math.hypot(float(G.nodes[n].get("x", 0)) - ex, float(G.nodes[n].get("y", 0)) - ey) <= radius_km]
    events.append(
        {
            "event_id": eid,
            "type": disaster_type,
            "severity": severity,
            "affected_nodes": affected_nodes[:20],
            "blocked_edges": blocked_pairs,
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "active": True,
        }
    )
    _write_events(events)

    for pair in blocked_pairs:
        if G.has_edge(pair[0], pair[1]):
            G.remove_edge(pair[0], pair[1])
        dstar_runtime.notify_edge_blocked(pair[0], pair[1])

    return eid


def get_affected_zones(G: nx.Graph, event: dict[str, Any]) -> list[str]:
    """Zones whose nodes intersect event affected_nodes."""
    aff = set(event.get("affected_nodes", []))
    zones: list[str] = []
    raw_zones = data_loader.read_evacuation_zones()
    for z in raw_zones:
        zid = z.get("zone_id", "")
        nodes = set(z.get("nodes", []))
        if aff & nodes:
            zones.append(zid)
    return zones


def compute_risk_score(node: str, active_events: list[dict]) -> float:
    """0.0 safe .. 1.0 critical based on proximity to active disasters."""
    risk = 0.0
    for ev in active_events:
        if not ev.get("active", True):
            continue
        if node in ev.get("affected_nodes", []):
            risk = max(risk, 0.85)
        sev = str(ev.get("severity", "low")).lower()
        sev_map = {"low": 0.15, "medium": 0.35, "high": 0.55, "critical": 0.75}
        boost = sev_map.get(sev, 0.2)
        for pair in ev.get("blocked_edges", []):
            if len(pair) >= 2 and node in (pair[0], pair[1]):
                risk = max(risk, 0.4 + boost * 0.3)
    return min(1.0, risk)
