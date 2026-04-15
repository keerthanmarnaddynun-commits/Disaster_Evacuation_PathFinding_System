from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.algorithm_selector import select_and_run
from algorithms.dijkstra import dijkstra
from core.data_loader import (
    append_rescue_log,
    load_city_graph,
    load_rescue_units,
    load_safe_zones,
    load_resources,
    save_resources,
    save_safe_zones,
    save_city_graph,
    save_rescue_units,
)
from core.graph_engine import load_graph, get_adjacency_list


class MissionManager:
    MISSIONS_FILE = Path("data/active_missions.json")

    def load(self) -> list[dict]:
        if not self.MISSIONS_FILE.exists():
            return []
        with open(self.MISSIONS_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("missions", [])

    def save(self, missions: list[dict]):
        payload = {"missions": missions}
        fd, tmp_path = tempfile.mkstemp(dir=self.MISSIONS_FILE.parent, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.MISSIONS_FILE)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _update_team(self, city: str, team_id: str, **updates) -> dict | None:
        teams = load_rescue_units(city)
        team = next((t for t in teams if t.get("unit_id") == team_id), None)
        if not team:
            return None
        team.update(updates)
        save_rescue_units(teams, city)
        return team

    def create_mission(
        self,
        team,
        target_node,
        target_name,
        path,
        path_names,
        algorithm_result,
        people_at_target,
        injury_level,
        city,
    ) -> dict:
        missions = self.load()
        now = datetime.now().isoformat(timespec="seconds")
        safe_zone = self._nearest_safe_zone(city, target_node)
        mission = {
            "mission_id": f"M{int(datetime.now().timestamp())}",
            "city": city,
            "team_id": team["unit_id"],
            "team_name": team["name"],
            "team_type": team["unit_type"],
            "target_node": target_node,
            "target_name": target_name,
            "path": path,
            "path_names": path_names,
            "original_path_length": max(0, len(path) - 1),
            "current_step": 0,
            "algorithm_used": algorithm_result["algorithm"],
            "why_selected": algorithm_result["why_selected"],
            "total_path_length": max(0, len(path) - 1),
            "nodes_explored": int(algorithm_result["nodes_explored"]),
            "time_ms": float(algorithm_result["runtime_ms"]),
            "people_at_target": int(people_at_target),
            "injury_level": injury_level,
            "status": "en_route",
            "phase": "to_victim",
            "dispatched_at": now,
            "arrived_at": None,
            "rescued_at": None,
            "completed_at": None,
            "fuel_used": 0,
            "used_air_edges": bool(algorithm_result.get("used_air_edges", False)),
            "replanned": False,
            "original_algorithm": algorithm_result["algorithm"],
            "safe_zone_id": safe_zone.get("id", ""),
            "safe_zone_name": safe_zone.get("name", ""),
            "safe_zone_node": safe_zone.get("node_id", team["base_node"]),
            "rescued_people": 0,
        }
        missions.append(mission)
        self.save(missions)
        self._update_team(city, team["unit_id"], status="dispatched")
        return mission

    def get_mission(self, mission_id) -> dict | None:
        return next((m for m in self.load() if m.get("mission_id") == mission_id), None)

    def advance_step(self, mission_id) -> dict:
        missions = self.load()
        mission = next(m for m in missions if m.get("mission_id") == mission_id)
        if mission.get("status") == "complete":
            return mission
        if mission["current_step"] < len(mission["path"]) - 1:
            mission["current_step"] += 1
        current_node = mission["path"][mission["current_step"]]
        if mission["current_step"] == len(mission["path"]) - 1:
            if mission.get("status") == "en_route":
                mission["status"] = "arrived"
                mission["arrived_at"] = datetime.now().isoformat(timespec="seconds")
            elif mission.get("status") == "returning":
                mission["status"] = "complete"
                mission["completed_at"] = datetime.now().isoformat(timespec="seconds")
        self.save(missions)
        team_updates = {"current_node": current_node}
        if mission.get("status") == "complete":
            team_updates["status"] = "available"
        self._update_team(mission["city"], mission["team_id"], **team_updates)
        return mission

    def confirm_rescue(self, mission_id, people_rescued) -> dict:
        missions = self.load()
        mission = next(m for m in missions if m.get("mission_id") == mission_id)
        if mission.get("status") != "arrived":
            raise ValueError("Rescue can only be confirmed for arrived missions.")
        if int(mission.get("rescued_people", 0)) > 0:
            raise ValueError("Rescue already confirmed for this mission.")
        mission["status"] = "rescued"
        mission["phase"] = "to_safe_zone"
        mission["rescued_at"] = datetime.now().isoformat(timespec="seconds")
        mission["fuel_used"] = mission["total_path_length"] * (3 if mission.get("used_air_edges") else 2)
        city = mission["city"]

        city_graph = load_city_graph(city)
        rescued_now = 0
        for node in city_graph.get("nodes", []):
            if node.get("id") == mission["target_node"]:
                current_stranded = int(node.get("people_stranded", 0))
                rescued_now = min(int(people_rescued), current_stranded)
                node["people_stranded"] = max(0, current_stranded - rescued_now)
                break
        mission["rescued_people"] = int(rescued_now)
        save_city_graph(city_graph, city)

        teams = load_rescue_units(city)
        team = next(t for t in teams if t["unit_id"] == mission["team_id"])
        team["fuel_remaining"] = max(0, int(team.get("fuel_remaining", 0)) - int(mission["fuel_used"]))
        if mission.get("injury_level", "low") in {"medium", "high", "critical"}:
            team["medical_kits"] = max(0, int(team.get("medical_kits", 0)) - 1)
        team["total_rescued"] = int(team.get("total_rescued", 0)) + int(rescued_now)
        save_rescue_units(teams, city)
        self._settle_to_safe_zone_and_consume_resources(city, mission, rescued_now)

        append_rescue_log(
            {
                "log_id": f"LOG-{mission['mission_id']}",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "city": city,
                "team_id": mission["team_id"],
                "team_name": mission["team_name"],
                "team_type": mission["team_type"],
                "from_node": mission["path"][0],
                "from_name": mission["path_names"][0],
                "to_node": mission["target_node"],
                "to_name": mission["target_name"],
                "algorithm_used": mission["algorithm_used"],
                "path_length": mission["total_path_length"],
                "nodes_explored": mission["nodes_explored"],
                "time_ms": mission["time_ms"],
                "people_rescued": int(rescued_now),
                "fuel_used": mission["fuel_used"],
                "medical_kits_used": 1 if mission.get("injury_level", "low") in {"medium", "high", "critical"} else 0,
                "knapsack_selected": False,
                "status": mission["status"],
            }
        )
        self.save(missions)
        return mission

    def start_return(self, mission_id) -> dict:
        missions = self.load()
        mission = next(m for m in missions if m.get("mission_id") == mission_id)
        mission["status"] = "returning"
        city_graph = load_city_graph(mission["city"])
        G = load_graph(city_graph)
        adj = get_adjacency_list(
            G,
            mode="balanced",
            disaster_events=[],
            unit_type="helicopter" if mission.get("team_type") == "helicopter" else "ground",
        )
        start = mission["target_node"]
        end = mission.get("safe_zone_node") or mission["path"][0]
        path, _ = dijkstra(adj, start, end)
        if not path:
            path = list(reversed(mission["path"]))
        node_names = {n["id"]: n.get("name", n["id"]) for n in city_graph.get("nodes", [])}
        mission["path"] = path
        mission["path_names"] = [node_names.get(n, n) for n in path]
        mission["current_step"] = 0
        self.save(missions)
        return mission

    def complete_mission(self, mission_id) -> dict:
        missions = self.load()
        mission = next(m for m in missions if m.get("mission_id") == mission_id)
        mission["status"] = "complete"
        mission["completed_at"] = datetime.now().isoformat(timespec="seconds")
        self._update_team(
            mission["city"],
            mission["team_id"],
            status="available",
            current_node=mission["path"][-1],
        )
        self.save(missions)
        return mission

    def get_active_missions_df(self) -> pd.DataFrame:
        return pd.DataFrame([m for m in self.load() if m.get("status") != "complete"])

    def get_completed_missions_df(self) -> pd.DataFrame:
        return pd.DataFrame([m for m in self.load() if m.get("status") == "complete"])

    def block_affects_mission(self, blocked_u, blocked_v) -> list[str]:
        affected: list[str] = []
        for m in self.load():
            if m.get("status") != "en_route":
                continue
            rem = m.get("path", [])[m.get("current_step", 0) :]
            for i in range(len(rem) - 1):
                if {rem[i], rem[i + 1]} == {blocked_u, blocked_v}:
                    affected.append(m["mission_id"])
                    break
        return affected

    def replan_mission(self, mission_id, G, disaster_events, positions, city_graph_data) -> dict:
        missions = self.load()
        mission = next(m for m in missions if m.get("mission_id") == mission_id)
        current_node = mission["path"][mission["current_step"]]
        result = select_and_run(
            G,
            current_node,
            mission["target_node"],
            disaster_events,
            positions,
            city_graph_data,
            unit_type="helicopter" if mission.get("team_type") == "helicopter" else "ground",
        )
        rec = result["recommended"]
        node_names = {n["id"]: n.get("name", n["id"]) for n in city_graph_data.get("nodes", [])}
        mission["path"] = rec["path"]
        mission["path_names"] = [node_names.get(n, n) for n in rec["path"]]
        mission["algorithm_used"] = rec["algorithm"]
        mission["why_selected"] = rec["why_selected"]
        mission["current_step"] = 0
        mission["total_path_length"] = rec["path_length"]
        mission["nodes_explored"] = rec["nodes_explored"]
        mission["time_ms"] = rec["runtime_ms"]
        mission["used_air_edges"] = rec.get("used_air_edges", False)
        mission["replanned"] = True
        self.save(missions)
        return mission

    def _nearest_safe_zone(self, city: str, from_node: str) -> dict:
        safe_zones = load_safe_zones(city)
        if not safe_zones:
            return {}
        city_graph = load_city_graph(city)
        G = load_graph(city_graph)
        adj = get_adjacency_list(G, mode="balanced", disaster_events=[])
        best_zone = safe_zones[0]
        best_cost = float("inf")
        for zone in safe_zones:
            target = zone.get("node_id")
            if not target:
                continue
            _, cost = dijkstra(adj, from_node, target)
            if cost < best_cost:
                best_cost = cost
                best_zone = zone
        return best_zone

    def _settle_to_safe_zone_and_consume_resources(self, city: str, mission: dict, rescued_count: int) -> None:
        if rescued_count <= 0:
            return
        safe_zones = load_safe_zones(city)
        zone = next((z for z in safe_zones if z.get("id") == mission.get("safe_zone_id")), None)
        if not zone:
            return
        zone["current_occupancy"] = int(zone.get("current_occupancy", 0)) + int(rescued_count)
        resources = zone.setdefault("resources", {})
        victims = zone.setdefault("victims", {"critical": 0, "high": 0, "medium": 0, "low": 0, "recovered": 0, "total": 0})
        injury = str(mission.get("injury_level", "medium")).lower()
        bucket = injury if injury in {"critical", "high", "medium", "low"} else "medium"
        victims[bucket] = int(victims.get(bucket, 0)) + int(rescued_count)
        victims["total"] = int(victims.get("total", 0)) + int(rescued_count)
        resources["food_packets"] = max(0, int(resources.get("food_packets", 0)) - int(rescued_count))
        resources["water_liters"] = max(0, int(resources.get("water_liters", 0)) - int(rescued_count))
        resources["medical_kits"] = max(0, int(resources.get("medical_kits", 0)) - max(1, int(rescued_count // 10)))
        save_safe_zones(safe_zones, city)

        res_data = load_resources()
        res_data.setdefault("distribution_log", []).append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": "consumed",
                "resource_id": "MULTI",
                "resource_name": "Safe-zone consumption",
                "quantity": int(rescued_count),
                "safe_zone_id": zone.get("id", ""),
                "safe_zone_name": zone.get("name", ""),
                "reason": f"Rescued civilians settled by {mission.get('team_name', 'team')}",
            }
        )
        save_resources(res_data)
