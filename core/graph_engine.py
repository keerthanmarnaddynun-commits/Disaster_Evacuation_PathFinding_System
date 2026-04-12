"""NetworkX city graph load/save and adjacency helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import networkx as nx

from core import data_loader


def load_graph(path: str | Path | None = None) -> nx.Graph:
    """Load city_graph.json into an undirected NetworkX graph with full edge attributes."""
    if path is None:
        raw = data_loader.read_city_graph()
    else:
        p = Path(path)
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)

    G = nx.Graph()
    city = raw.get("city_name", "")
    G.graph["city_name"] = city

    for n in raw.get("nodes", []):
        nid = n["id"]
        G.add_node(
            nid,
            name=n.get("name", nid),
            node_type=n.get("type", "intersection"),
            x=float(n.get("x", 0)),
            y=float(n.get("y", 0)),
            zone=n.get("zone", ""),
            elevation=float(n.get("elevation", 0)),
            population_density=float(n.get("population_density", 0)),
        )

    for e in raw.get("edges", []):
        u, v = e["source"], e["target"]
        dist = float(e.get("distance_km", 1))
        base_t = float(e.get("base_travel_time_min", 1))
        cap = float(e.get("capacity", 100))
        congestion = float(e.get("congestion_factor", 1.0))
        road_name = e.get("road_name", "")
        road_type = e.get("road_type", "local")
        bidirectional = e.get("bidirectional", True)

        attrs = {
            "distance_km": dist,
            "base_travel_time_min": base_t,
            "capacity": cap,
            "congestion_factor": congestion,
            "road_name": road_name,
            "road_type": road_type,
            "bidirectional": bidirectional,
        }
        if G.has_edge(u, v):
            continue
        G.add_edge(u, v, **attrs)

    return G


def save_graph(G: nx.Graph, path: str | Path | None = None) -> None:
    """Persist graph nodes/edges back to JSON (atomic)."""
    out_path = Path(path) if path else data_loader.DATA_DIR / "city_graph.json"
    nodes_out = []
    for nid, data in G.nodes(data=True):
        nodes_out.append(
            {
                "id": nid,
                "name": data.get("name", nid),
                "type": data.get("node_type", "intersection"),
                "x": data.get("x", 0),
                "y": data.get("y", 0),
                "zone": data.get("zone", ""),
                "elevation": data.get("elevation", 0),
                "population_density": data.get("population_density", 0),
            }
        )
    nodes_out.sort(key=lambda x: x["id"])

    seen: set[tuple[str, str]] = set()
    edges_out = []
    for u, v, ed in G.edges(data=True):
        a, b = (u, v) if u < v else (v, u)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        edges_out.append(
            {
                "source": a,
                "target": b,
                "road_name": ed.get("road_name", ""),
                "distance_km": float(ed.get("distance_km", 0)),
                "base_travel_time_min": float(ed.get("base_travel_time_min", 0)),
                "capacity": float(ed.get("capacity", 0)),
                "road_type": ed.get("road_type", "local"),
                "bidirectional": ed.get("bidirectional", True),
                "congestion_factor": float(ed.get("congestion_factor", 1.0)),
            }
        )

    payload = {
        "city_name": G.graph.get("city_name", "Veridian City"),
        "nodes": nodes_out,
        "edges": edges_out,
    }
    if path is None:
        data_loader.write_json("city_graph.json", payload)
    else:
        data_loader.write_json_path(Path(path), payload)


def _edge_key(u: str, v: str) -> tuple[str, str]:
    return (u, v) if u <= v else (v, u)


def get_edge_weight(
    G: nx.Graph,
    u: str,
    v: str,
    mode: str,
    *,
    active_events: list[dict] | None = None,
) -> float:
    """
    Edge weight for pathfinding.
    fastest: base travel time scaled by congestion.
    safest: heavy penalty near disaster-affected nodes.
    balanced: combo of time, distance, and safety.
    """
    if not G.has_edge(u, v):
        return float("inf")

    ed = G.edges[u, v]
    base_t = float(ed.get("base_travel_time_min", 1))
    dist = float(ed.get("distance_km", 0))
    congestion = float(ed.get("congestion_factor", 1.0))
    cap = max(float(ed.get("capacity", 1)), 1.0)
    road_type = ed.get("road_type", "local")

    affected: set[str] = set()
    if active_events:
        for ev in active_events:
            if ev.get("active"):
                affected.update(ev.get("affected_nodes", []))

    time_est = base_t * congestion * (1.0 + 200.0 / cap)

    if mode == "fastest":
        if road_type == "highway":
            time_est *= 0.92
        elif road_type == "bridge":
            time_est *= 1.05
        return time_est

    if mode == "safest":
        pen = 1.0
        if u in affected or v in affected:
            pen += 8.0
        if road_type == "bridge":
            pen += 2.0
        low_elev = min(
            float(G.nodes[u].get("elevation", 0)),
            float(G.nodes[v].get("elevation", 0)),
        )
        if low_elev < 10:
            pen += 3.0
        return time_est * pen

    if mode == "balanced":
        safety_pen = 0.0
        if u in affected or v in affected:
            safety_pen += 5.0
        low_elev = min(
            float(G.nodes[u].get("elevation", 0)),
            float(G.nodes[v].get("elevation", 0)),
        )
        if low_elev < 12:
            safety_pen += 1.5
        dist_norm = dist * 2.0
        return 0.45 * time_est + 0.35 * safety_pen + 0.20 * dist_norm

    return time_est


def add_node(
    G: nx.Graph,
    node_id: str,
    *,
    name: str = "",
    node_type: str = "intersection",
    x: float = 0.0,
    y: float = 0.0,
    zone: str = "",
    elevation: float = 0.0,
    population_density: float = 0.0,
) -> None:
    G.add_node(
        node_id,
        name=name or node_id,
        node_type=node_type,
        x=x,
        y=y,
        zone=zone,
        elevation=elevation,
        population_density=population_density,
    )


def add_edge(
    G: nx.Graph,
    u: str,
    v: str,
    *,
    distance_km: float = 1.0,
    base_travel_time_min: float = 5.0,
    capacity: float = 500.0,
    road_name: str = "",
    road_type: str = "local",
    bidirectional: bool = True,
    congestion_factor: float = 1.0,
) -> None:
    G.add_edge(
        u,
        v,
        distance_km=distance_km,
        base_travel_time_min=base_travel_time_min,
        capacity=capacity,
        road_name=road_name,
        road_type=road_type,
        bidirectional=bidirectional,
        congestion_factor=congestion_factor,
    )


def remove_edge(G: nx.Graph, u: str, v: str) -> None:
    if G.has_edge(u, v):
        G.remove_edge(u, v)


def get_neighbors(G: nx.Graph, node: str) -> list[str]:
    """Adjacency list (node ids) for BFS/DFS imports."""
    return list(G.neighbors(node))


def to_unweighted_adjacency(G: nx.Graph) -> dict[str, list[str]]:
    """Adjacency list {node: [neighbors]} for BFS/DFS."""
    return {n: list(G.neighbors(n)) for n in G.nodes()}


def to_weighted_adjacency(
    G: nx.Graph,
    mode: str,
    *,
    active_events: list[dict] | None = None,
) -> dict[str, list[tuple[str, float]]]:
    """Weighted adjacency for Dijkstra/A*."""
    adj: dict[str, list[tuple[str, float]]] = {n: [] for n in G.nodes()}
    for u, v in G.edges():
        w = get_edge_weight(G, u, v, mode, active_events=active_events)
        if math.isinf(w):
            continue
        adj[u].append((v, w))
        adj[v].append((u, w))
    return adj


def node_positions(G: nx.Graph) -> dict[str, tuple[float, float]]:
    """Positions dict for A* heuristic: {node_id: (x, y)}."""
    pos = {}
    for n, data in G.nodes(data=True):
        pos[n] = (float(data.get("x", 0)), float(data.get("y", 0)))
    return pos
