from __future__ import annotations

import pandas as pd

from algorithms.dijkstra import dijkstra, dijkstra_all_distances
from core.graph_engine import get_adjacency_list

INJURY_WEIGHT = {"critical": 10, "high": 7, "medium": 4, "low": 1, "none": 0}


def nearest_victim_first(G, team_node, victim_nodes, disaster_events) -> pd.DataFrame:
    adj = get_adjacency_list(G, "balanced", disaster_events)
    distances = dijkstra_all_distances(adj, team_node)
    rows = []
    for node in victim_nodes:
        rows.append(
            {
                "node_id": node["id"],
                "node_name": node.get("name", node["id"]),
                "distance": float(distances.get(node["id"], float("inf"))),
                "people_stranded": int(node.get("people_stranded", 0)),
                "injury_level": node.get("injury_level", "none"),
                "survival_chance": float(node.get("survival_chance", 0.5)),
                "rescue_cost": int(node.get("rescue_cost", 1)),
            }
        )
    return pd.DataFrame(rows).sort_values(["distance", "people_stranded"], ascending=[True, False]).reset_index(drop=True)


def highest_priority_first(victim_nodes, city_graph_data) -> pd.DataFrame:
    rows = []
    for node in victim_nodes:
        injury = str(node.get("injury_level", "none")).lower()
        score = (INJURY_WEIGHT.get(injury, 1) * float(node.get("survival_chance", 0.5))) / max(1, int(node.get("rescue_cost", 1)))
        rows.append(
            {
                "node_id": node["id"],
                "node_name": node.get("name", node["id"]),
                "priority_score": float(score),
                "people_stranded": int(node.get("people_stranded", 0)),
                "injury_level": injury,
                "rescue_cost": int(node.get("rescue_cost", 1)),
            }
        )
    return pd.DataFrame(rows).sort_values(["priority_score", "people_stranded"], ascending=[False, False]).reset_index(drop=True)


def greedy_recommendation(strategy, G, team_node, victim_nodes, disaster_events, city_graph_data) -> str:
    if strategy == "Nearest Victim First":
        df = nearest_victim_first(G, team_node, victim_nodes, disaster_events)
    else:
        df = highest_priority_first(victim_nodes, city_graph_data)
    if df.empty:
        return ""
    return str(df.iloc[0]["node_id"])


def nearest_team_to_target(G, target_node, available_teams, disaster_events, unit_types) -> dict:
    best = None
    for team in available_teams:
        unit_type = unit_types.get(team["unit_id"], "ground")
        adj = get_adjacency_list(G, "balanced", disaster_events, unit_type=unit_type)
        path, cost = dijkstra(adj, team["current_node"], target_node)
        if not path:
            continue
        rec = {"team": team, "cost": float(cost), "path": path}
        if best is None or rec["cost"] < best["cost"]:
            best = rec
    return best or {}
