from __future__ import annotations

import math

INJURY_WEIGHT = {"critical": 10, "high": 7, "medium": 4, "low": 1, "none": 0}


def knapsack_01(victims: list[dict], capacity: int) -> dict:
    n = len(victims)
    w_cap = max(0, int(capacity))
    dp = [[0.0 for _ in range(w_cap + 1)] for _ in range(n + 1)]
    for i in range(1, n + 1):
        wt = int(victims[i - 1]["rescue_cost"])
        val = float(victims[i - 1]["rescue_value"])
        for w in range(w_cap + 1):
            if wt <= w:
                dp[i][w] = max(dp[i - 1][w], dp[i - 1][w - wt] + val)
            else:
                dp[i][w] = dp[i - 1][w]

    selected_idx = []
    w = w_cap
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            selected_idx.append(i - 1)
            w -= int(victims[i - 1]["rescue_cost"])
    selected_idx.reverse()

    selected = [victims[i] for i in selected_idx]
    not_selected = [victims[i] for i in range(n) if i not in selected_idx]
    total_cost = sum(int(v["rescue_cost"]) for v in selected)
    return {
        "selected": selected,
        "not_selected": not_selected,
        "total_value": float(dp[n][w_cap]),
        "total_cost": int(total_cost),
        "dp_table": dp,
        "traceback": selected_idx,
    }


def build_victim_list(city_graph_data, node_ids: list[str], disaster_events: list) -> list[dict]:
    node_map = {n["id"]: n for n in city_graph_data.get("nodes", [])}
    victims = []
    for node_id in node_ids:
        node = node_map.get(node_id, {})
        people = int(node.get("people_stranded", 0))
        injury = str(node.get("injury_level", "none")).lower()
        survival = float(node.get("survival_chance", 0.5))
        rescue_cost = int(node.get("rescue_cost", 1))
        rescue_value = INJURY_WEIGHT.get(injury, 1) * survival * math.log(people + 1)
        victims.append(
            {
                "node_id": node_id,
                "name": node.get("name", node_id),
                "rescue_cost": rescue_cost,
                "rescue_value": float(rescue_value),
                "people_stranded": people,
                "injury_level": injury,
            }
        )
    return victims


def knapsack_supply(resources: list[dict], budget: int) -> dict:
    items = []
    for r in resources:
        items.append(
            {
                "node_id": r.get("resource_id"),
                "name": r.get("name"),
                "rescue_cost": int(r.get("cost_per_unit", 1)),
                "rescue_value": float(r.get("value_per_unit", 1)),
                "people_stranded": int(r.get("max_available", 1)),
                "injury_level": "none",
            }
        )
    return knapsack_01(items, budget)
