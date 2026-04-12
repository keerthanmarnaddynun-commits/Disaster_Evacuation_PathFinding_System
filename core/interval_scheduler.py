"""
Interval scheduling for rescue operations using explicit priority queues.
"""

from __future__ import annotations

import bisect
import copy
import math
from dataclasses import dataclass
from typing import Any, Optional

import networkx as nx

from algorithms.Dijkstra import dijkstra

from core import data_loader, graph_engine
from core.priority_queue import MaxHeapPQ, MinHeapPQ


@dataclass
class RescueMission:
    mission_id: str
    zone: str
    start_time: float
    end_time: float
    priority: int
    people_count: int
    required_unit_type: str
    assigned_unit: Optional[str] = None
    status: str = "pending"

    def duration(self) -> float:
        return self.end_time - self.start_time

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RescueMission):
            return NotImplemented
        return (self.priority, self.start_time, self.mission_id) < (
            other.priority,
            other.start_time,
            other.mission_id,
        )


def _missions_from_dicts(raw: list[dict[str, Any]]) -> list[RescueMission]:
    out: list[RescueMission] = []
    for r in raw:
        out.append(
            RescueMission(
                mission_id=str(r["mission_id"]),
                zone=str(r["zone"]),
                start_time=float(r["start_time"]),
                end_time=float(r["end_time"]),
                priority=int(r["priority"]),
                people_count=int(r["people_count"]),
                required_unit_type=str(r.get("required_unit_type", "any")),
                assigned_unit=r.get("assigned_unit"),
                status=str(r.get("status", "pending")),
            )
        )
    return out


def _missions_to_dicts(ms: list[RescueMission]) -> list[dict[str, Any]]:
    return [
        {
            "mission_id": m.mission_id,
            "zone": m.zone,
            "start_time": m.start_time,
            "end_time": m.end_time,
            "priority": m.priority,
            "people_count": m.people_count,
            "required_unit_type": m.required_unit_type,
            "assigned_unit": m.assigned_unit,
            "status": m.status,
        }
        for m in ms
    ]


def _merge_scheduled(missions: list[RescueMission], scheduled: list[RescueMission]) -> None:
    smap = {m.mission_id: m for m in scheduled}
    for m in missions:
        if m.mission_id in smap:
            u = smap[m.mission_id]
            m.assigned_unit = u.assigned_unit
            m.status = u.status


class RescueScheduler:
    """
    Weighted / greedy interval scheduling with optional graph-based dispatch.
    """

    def __init__(
        self,
        missions: list[RescueMission],
        units: list[dict[str, Any]],
        G: Optional[nx.Graph] = None,
    ) -> None:
        self.missions = list(missions)
        self.units = copy.deepcopy(units)
        self.G = G
        self.scheduled: list[RescueMission] = []
        self.mission_queue: MinHeapPQ[RescueMission] = MinHeapPQ()
        self._urgency = MaxHeapPQ()
        for m in self.missions:
            if m.status == "pending":
                self._urgency.push(float(m.priority), m.mission_id)
        self._build_priority_queue()

    def _build_priority_queue(self) -> None:
        self.mission_queue = MinHeapPQ()
        for m in self.missions:
            if m.status == "pending":
                key = float(m.priority) + m.start_time / 1_000_000.0
                self.mission_queue.push(key, m)

    def schedule(self, strategy: str = "priority_first", *, persist: bool = True) -> list[RescueMission]:
        self.scheduled = []
        if strategy == "maximize_missions":
            out = self._schedule_maximize_missions()
        elif strategy == "maximize_people":
            out = self._schedule_maximize_people()
        else:
            out = self._schedule_priority_first()
        _merge_scheduled(self.missions, out)
        if persist:
            persist_missions(self.missions)
        return out

    def _unit_matches(self, unit: dict[str, Any], req: str) -> bool:
        if req == "any":
            return True
        return str(unit.get("type", "")).lower() == req.lower()

    def _schedule_maximize_missions(self) -> list[RescueMission]:
        """Greedy by earliest finish time per unit."""
        pending = [m for m in self.missions if m.status == "pending"]
        pending.sort(key=lambda m: (m.end_time, m.start_time))
        last_finish: dict[str, float] = {}
        out: list[RescueMission] = []
        for m in pending:
            placed = False
            for u in self.units:
                uid = str(u.get("unit_id", ""))
                if not self._unit_matches(u, m.required_unit_type):
                    continue
                lf = last_finish.get(uid, -math.inf)
                if m.start_time >= lf:
                    m2 = copy.copy(m)
                    m2.assigned_unit = uid
                    m2.status = "scheduled"
                    last_finish[uid] = m.end_time
                    out.append(m2)
                    placed = True
                    break
            if not placed:
                pass
        self.scheduled = out
        return out

    def _schedule_maximize_people(self) -> list[RescueMission]:
        """Weighted interval scheduling (single-timeline relaxation)."""
        pending = [m for m in self.missions if m.status == "pending"]
        pending.sort(key=lambda m: m.end_time)
        ends = [m.end_time for m in pending]
        starts = [m.start_time for m in pending]

        def p_of(i: int) -> int:
            return bisect.bisect_right(ends[:i], starts[i]) - 1

        n = len(pending)
        if n == 0:
            self.scheduled = []
            return []
        dp = [0] * n
        take = [False] * n
        dp[0] = pending[0].people_count
        take[0] = True
        for i in range(1, n):
            pj = p_of(i)
            prev_w = dp[pj] if pj >= 0 else 0
            with_i = pending[i].people_count + prev_w
            without_i = dp[i - 1]
            if with_i >= without_i:
                dp[i] = with_i
                take[i] = True
            else:
                dp[i] = without_i
                take[i] = False

        chosen: list[RescueMission] = []
        i = n - 1
        while i >= 0:
            if take[i]:
                chosen.append(pending[i])
                i = p_of(i)
            else:
                i -= 1
        chosen.reverse()

        out: list[RescueMission] = []
        last_finish: dict[str, float] = {}
        for m in chosen:
            placed = False
            for u in self.units:
                uid = str(u.get("unit_id", ""))
                if not self._unit_matches(u, m.required_unit_type):
                    continue
                lf = last_finish.get(uid, -math.inf)
                if m.start_time >= lf:
                    m2 = copy.copy(m)
                    m2.assigned_unit = uid
                    m2.status = "scheduled"
                    last_finish[uid] = m.end_time
                    out.append(m2)
                    placed = True
                    break
        self.scheduled = out
        return out

    def _nearest_unit_dispatch(self, mission: RescueMission) -> Optional[str]:
        if self.G is None:
            return None
        zones = data_loader.read_evacuation_zones()
        zone = next((z for z in zones if z.get("zone_id") == mission.zone), None)
        if zone is None:
            return None
        events = data_loader.read_disaster_events()
        wadj = graph_engine.to_weighted_adjacency(self.G, "fastest", active_events=events)
        best_u: Optional[str] = None
        best_c = float("inf")
        zone_nodes = set(zone.get("nodes", []))
        candidates = [u for u in self.units if u.get("status") == "available"]
        for unit in candidates:
            if not self._unit_matches(unit, mission.required_unit_type):
                continue
            loc = unit.get("location_node")
            if loc not in self.G:
                continue
            for target in zone_nodes:
                if target not in self.G:
                    continue
                path, cost = dijkstra(wadj, loc, target)
                if path and cost < best_c:
                    best_c = cost
                    best_u = str(unit.get("unit_id"))
        return best_u

    def _schedule_priority_first(self) -> list[RescueMission]:
        """Priority order using MinHeapPQ; dispatch nearest compatible unit."""
        pq = MinHeapPQ[RescueMission]()
        for m in self.missions:
            if m.status == "pending":
                pq.push(float(m.priority) + m.start_time / 1e6, m)

        last_finish: dict[str, float] = {}
        out: list[RescueMission] = []

        while not pq.is_empty():
            _, m = pq.pop()
            if m.status != "pending":
                continue
            uid = self._nearest_unit_dispatch(m)
            if uid is None:
                for u in self.units:
                    cand = str(u.get("unit_id", ""))
                    if self._unit_matches(u, m.required_unit_type):
                        uid = cand
                        break
            if uid is None:
                continue
            lf = last_finish.get(uid, -math.inf)
            if m.start_time < lf:
                continue
            m2 = copy.copy(m)
            m2.assigned_unit = uid
            m2.status = "scheduled"
            last_finish[uid] = m.end_time
            out.append(m2)

        self.scheduled = out
        return out

    def get_schedule_timeline(self) -> dict[str, list[dict[str, Any]]]:
        timeline: dict[str, list[dict[str, Any]]] = {}
        for m in self.scheduled:
            uid = m.assigned_unit or "unassigned"
            timeline.setdefault(uid, []).append(
                {
                    "mission_id": m.mission_id,
                    "zone": m.zone,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "people_count": m.people_count,
                    "priority": m.priority,
                }
            )
        for k in timeline:
            timeline[k].sort(key=lambda x: x["start_time"])
        return timeline

    def get_statistics(self) -> dict[str, Any]:
        scheduled_ids = {m.mission_id for m in self.scheduled}
        pending = [m for m in self.missions if m.mission_id not in scheduled_ids and m.status != "cancelled"]
        people_sched = sum(m.people_count for m in self.scheduled)
        people_pending = sum(m.people_count for m in pending)
        crit = sum(1 for m in pending if m.priority == 1)

        horizon = max((m.end_time for m in self.missions), default=1.0)
        util: dict[str, float] = {}
        for u in self.units:
            uid = str(u.get("unit_id", ""))
            blocks = [m for m in self.scheduled if m.assigned_unit == uid]
            busy = sum(max(0.0, m.end_time - m.start_time) for m in blocks)
            util[uid] = min(1.0, busy / max(horizon, 1.0))

        return {
            "total_missions_scheduled": len(self.scheduled),
            "total_missions_pending": len(pending),
            "total_people_scheduled": people_sched,
            "total_people_unscheduled": people_pending,
            "unit_utilization": util,
            "critical_unscheduled": crit,
        }

    def add_mission(self, mission: RescueMission) -> None:
        self.missions.append(mission)
        data_loader.write_rescue_missions(_missions_to_dicts(self.missions))
        self._build_priority_queue()

    def cancel_mission(self, mission_id: str) -> None:
        for m in self.missions:
            if m.mission_id == mission_id:
                m.status = "cancelled"
        data_loader.write_rescue_missions(_missions_to_dicts(self.missions))

    def reoptimize(self) -> None:
        """Re-run priority_first after external changes."""
        self.missions = load_missions_from_disk()
        self.units = copy.deepcopy(data_loader.read_rescue_units())
        self.schedule("priority_first")


def load_missions_from_disk() -> list[RescueMission]:
    return _missions_from_dicts(data_loader.read_rescue_missions())


def persist_missions(missions: list[RescueMission]) -> None:
    data_loader.write_rescue_missions(_missions_to_dicts(missions))
