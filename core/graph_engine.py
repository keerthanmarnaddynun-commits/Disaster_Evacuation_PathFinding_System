from __future__ import annotations

from typing import Any

import networkx as nx

from core.disaster_manager import compute_risk_score, get_all_blocked_edges


def load_graph(city_graph_data: dict) -> nx.Graph:
    """
    Build networkx Graph from city_graph.json dict.
    Edge weight = base_travel_time_min by default.
    """
    G = nx.Graph()
    for n in city_graph_data.get("nodes", []):
        G.add_node(
            n["id"],
            **{
                "id": n["id"],
                "name": n.get("name", n["id"]),
                "type": n.get("type", "intersection"),
                "x": float(n.get("x", 0.0)),
                "y": float(n.get("y", 0.0)),
                "zone": n.get("zone", ""),
                "elevation": int(n.get("elevation", 0)),
                "population_density": int(n.get("population_density", 0)),
                "people_stranded": int(n.get("people_stranded", 0)),
                "injury_level": n.get("injury_level", "none"),
                "rescue_cost": int(n.get("rescue_cost", 5)),
                "survival_chance": float(n.get("survival_chance", 0.6)),
                "helipad": bool(n.get("helipad", False)),
            },
        )
    for e in city_graph_data.get("edges", []):
        u = e["source"]
        v = e["target"]
        G.add_edge(
            u,
            v,
            road_name=e.get("road_name", f"{u}-{v}"),
            distance_km=float(e.get("distance_km", 1.0)),
            base_travel_time_min=float(e.get("base_travel_time_min", 1.0)),
            capacity=float(e.get("capacity", 500)),
            road_type=e.get("road_type", "local"),
            air_only=bool(e.get("air_only", False)),
            bidirectional=bool(e.get("bidirectional", True)),
            edge_load=float(e.get("edge_load", 0.0)),
        )
    return G


def get_positions(city_graph_data: dict) -> dict:
    return {n["id"]: (float(n.get("x", 0.0)), float(n.get("y", 0.0))) for n in city_graph_data.get("nodes", [])}


def get_node_metadata(G: nx.Graph, node_id: str) -> dict:
    return dict(G.nodes[node_id])


def _edge_key(u: str, v: str) -> tuple[str, str]:
    return (u, v) if u <= v else (v, u)


def get_adjacency_list(
    G: nx.Graph,
    mode: str = "fastest",
    disaster_events: list | None = None,
    positions: dict | None = None,
    unit_type: str | None = None,
) -> dict:
    """
    Convert nx.Graph to adjacency list for algorithm consumption.

    mode="fastest":  weight = base_travel_time_min * congestion_factor
    mode="safest":   weight = base_travel_time_min + (risk_score * 100)
    mode="balanced": weight = 0.5*time + 0.3*risk*50 + 0.2*distance*10
    Blocked edges (from disaster_events): weight = 999999 (passable but penalized heavily)
    Return format: {node_id: [(neighbor_id, weight), ...]}
    """
    events = disaster_events or []
    blocked = get_all_blocked_edges(events)

    # crude congestion: edge_load/capacity. edge_load defaults to 0; pages can mutate if desired.
    adj: dict[str, list[tuple[str, float]]] = {n: [] for n in G.nodes}
    for u, v, data in G.edges(data=True):
        if unit_type == "ground" and bool(data.get("air_only", False)):
            continue
        base_time = float(data.get("base_travel_time_min", 1.0))
        distance = float(data.get("distance_km", 1.0))
        capacity = float(data.get("capacity", 500.0))
        load = float(data.get("edge_load", 0.0))
        congestion_factor = 1.0 + min(1.5, (load / capacity) if capacity > 0 else 0.0)

        risk_u = compute_risk_score(u, events, G)
        risk_v = compute_risk_score(v, events, G)
        risk = (risk_u + risk_v) / 2.0

        if mode == "fastest":
            w = base_time * congestion_factor
        elif mode == "safest":
            w = base_time + (risk * 100.0)
        elif mode == "balanced":
            w = 0.5 * base_time + 0.3 * risk * 50.0 + 0.2 * distance * 10.0
        else:
            w = base_time

        if _edge_key(u, v) in blocked:
            w = 999999.0

        adj[u].append((v, float(w)))
        adj[v].append((u, float(w)))

    return adj


def get_unweighted_adjacency(G: nx.Graph, disaster_events: list | None = None, unit_type: str | None = None) -> dict:
    """
    For BFS/DFS: {node_id: [neighbor_id, ...]} skipping blocked/unit-incompatible edges.
    """
    events = disaster_events or []
    blocked = get_all_blocked_edges(events)
    adj: dict[str, list[str]] = {n: [] for n in G.nodes}
    for u, v, data in G.edges(data=True):
        if unit_type == "ground" and bool(data.get("air_only", False)):
            continue
        if _edge_key(u, v) in blocked:
            continue
        adj[u].append(v)
        adj[v].append(u)
    return adj


def get_edge_attrs(G: nx.Graph, u: str, v: str) -> dict[str, Any]:
    if G.has_edge(u, v):
        return dict(G.edges[u, v])
    return {}


def get_edge_distance_km(G: nx.Graph, u: str, v: str) -> float:
    return float(get_edge_attrs(G, u, v).get("distance_km", 0.0))


def get_edge_time_min(G: nx.Graph, u: str, v: str) -> float:
    return float(get_edge_attrs(G, u, v).get("base_travel_time_min", 0.0))


def get_edge_capacity(G: nx.Graph, u: str, v: str) -> float:
    return float(get_edge_attrs(G, u, v).get("capacity", 1.0))

