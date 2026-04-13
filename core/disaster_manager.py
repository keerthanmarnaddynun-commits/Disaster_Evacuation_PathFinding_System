from __future__ import annotations

from collections import deque
from datetime import datetime

import networkx as nx


_SEVERITY_MULT = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}


def _edge_key(u: str, v: str) -> tuple[str, str]:
    return (u, v) if u <= v else (v, u)


def get_all_blocked_edges(disaster_events) -> set[tuple]:
    """
    Return set of (u,v) tuples that are currently blocked (active events only).
    """
    out: set[tuple[str, str]] = set()
    for e in disaster_events or []:
        if not e.get("active", False):
            continue
        for u, v in e.get("blocked_edges", []):
            out.add(_edge_key(u, v))
    return out


def compute_risk_score(node_id, active_events, G) -> float:
    """
    0.0–1.0. Higher if node is in affected_nodes or adjacent to blocked_edges.
    Severity multiplier: critical=1.0, high=0.75, medium=0.5, low=0.25.
    """
    events = [e for e in (active_events or []) if e.get("active", False)]
    if not events:
        return 0.0

    base = 0.0
    for e in events:
        sev = str(e.get("severity", "low")).lower()
        mult = _SEVERITY_MULT.get(sev, 0.25)

        affected = set(e.get("affected_nodes", []))
        if node_id in affected:
            base = max(base, 1.0 * mult)

        blocked = {tuple(pair) for pair in e.get("blocked_edges", [])}
        # If node touches any blocked edge, it is at elevated risk.
        for u, v in blocked:
            if node_id == u or node_id == v:
                base = max(base, 0.8 * mult)
                break

        # Adjacent to affected nodes: small bump
        for a in affected:
            if G is not None and G.has_node(node_id) and G.has_node(a) and G.has_edge(node_id, a):
                base = max(base, 0.6 * mult)
                break

    return max(0.0, min(1.0, float(base)))


def block_road(u, v, reason, disaster_events) -> list:
    """
    Add edge to blocked_edges of most recent active event (or create new event).
    Return updated disaster_events list.
    """
    events = list(disaster_events or [])
    active = [e for e in events if e.get("active", False)]
    if active:
        target = active[-1]
    else:
        target = {
            "event_id": f"EVT-{len(events) + 1:03d}",
            "type": str(reason or "congestion"),
            "severity": "low",
            "affected_nodes": [],
            "blocked_edges": [],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "active": True,
        }
        events.append(target)

    blocked_edges = target.setdefault("blocked_edges", [])
    pair = [u, v]
    rev = [v, u]
    if pair not in blocked_edges and rev not in blocked_edges:
        blocked_edges.append(pair)
    return events


def unblock_road(u, v, disaster_events) -> list:
    """
    Remove from all blocked_edges lists. Return updated list.
    """
    events = list(disaster_events or [])
    for e in events:
        be = e.get("blocked_edges", [])
        e["blocked_edges"] = [pair for pair in be if not ({pair[0], pair[1]} == {u, v})]
    return events


def spread_disaster(G: nx.Graph, epicenter_node, radius_hops, disaster_type, severity) -> dict:
    """
    BFS from epicenter up to radius_hops. Block all edges within radius.
    Return new disaster event dict.
    """
    radius = int(radius_hops)
    visited = {epicenter_node: 0}
    q = deque([epicenter_node])
    affected_nodes: set[str] = {epicenter_node}
    blocked: set[tuple[str, str]] = set()

    while q:
        node = q.popleft()
        depth = visited[node]
        if depth >= radius:
            continue
        for nbr in G.neighbors(node):
            blocked.add(_edge_key(node, nbr))
            if nbr not in visited:
                visited[nbr] = depth + 1
                affected_nodes.add(nbr)
                q.append(nbr)

    return {
        "event_id": f"EVT-{datetime.now().strftime('%H%M%S')}",
        "type": str(disaster_type).lower(),
        "severity": str(severity).lower(),
        "affected_nodes": sorted(affected_nodes),
        "blocked_edges": [[u, v] for (u, v) in sorted(blocked)],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "active": True,
    }

