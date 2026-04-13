from __future__ import annotations

def path_uses_edge(path: list[str], u: str, v: str) -> bool:
    if not path or len(path) < 2:
        return False
    for i in range(len(path) - 1):
        if {path[i], path[i + 1]} == {u, v}:
            return True
    return False


def block_road_live(G, u, v, active_missions) -> dict:
    if G.has_edge(u, v):
        G.edges[u, v]["blocked_live"] = True
    affected = []
    for mission in active_missions:
        if mission.get("status") not in {"en_route", "returning"}:
            continue
        remain = mission.get("path", [])[mission.get("current_step", 0) :]
        if path_uses_edge(remain, u, v):
            affected.append(mission.get("mission_id", ""))
    return {"blocked": (u, v), "affected_missions": affected}


def restore_road_live(G, u, v) -> None:
    if not G.has_edge(u, v):
        G.add_edge(u, v, distance_km=1.0, base_travel_time_min=3.0, capacity=500.0, road_name=f"{u}-{v}", road_type="local")
