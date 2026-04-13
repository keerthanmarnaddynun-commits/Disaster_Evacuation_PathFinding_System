from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.algorithm_selector import select_and_run
from core.data_loader import (
    append_rescue_log,
    load_city_graph,
    load_rescue_units,
    save_city_graph,
    save_rescue_units,
)


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
            "dispatched_at": now,
            "arrived_at": None,
            "rescued_at": None,
            "completed_at": None,
            "fuel_used": 0,
            "used_air_edges": bool(algorithm_result.get("used_air_edges", False)),
            "replanned": False,
            "original_algorithm": algorithm_result["algorithm"],
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
        if mission["current_step"] < len(mission["path"]) - 1:
            mission["current_step"] += 1
        current_node = mission["path"][mission["current_step"]]
        if mission["current_step"] == len(mission["path"]) - 1:
            mission["status"] = "arrived"
            mission["arrived_at"] = datetime.now().isoformat(timespec="seconds")
        self.save(missions)
        self._update_team(mission["city"], mission["team_id"], current_node=current_node)
        return mission

    def confirm_rescue(self, mission_id, people_rescued) -> dict:
        missions = self.load()
        mission = next(m for m in missions if m.get("mission_id") == mission_id)
        mission["status"] = "rescued"
        mission["rescued_at"] = datetime.now().isoformat(timespec="seconds")
        mission["fuel_used"] = mission["total_path_length"] * (3 if mission.get("used_air_edges") else 2)
        city = mission["city"]

        city_graph = load_city_graph(city)
        for node in city_graph.get("nodes", []):
            if node.get("id") == mission["target_node"]:
                node["people_stranded"] = 0
                break
        save_city_graph(city_graph, city)

        teams = load_rescue_units(city)
        team = next(t for t in teams if t["unit_id"] == mission["team_id"])
        team["fuel_remaining"] = max(0, int(team.get("fuel_remaining", 0)) - int(mission["fuel_used"]))
        if mission.get("injury_level", "low") in {"medium", "high", "critical"}:
            team["medical_kits"] = max(0, int(team.get("medical_kits", 0)) - 1)
        team["total_rescued"] = int(team.get("total_rescued", 0)) + int(people_rescued)
        save_rescue_units(teams, city)

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
                "people_rescued": int(people_rescued),
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
        mission["path"] = list(reversed(mission["path"]))
        mission["path_names"] = list(reversed(mission["path_names"]))
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
