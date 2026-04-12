"""Atomic read/write for JSON and CSV under data/."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _PROJECT_ROOT / "data"


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".csv")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_json(filename: str) -> Any:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(filename: str, data: Any) -> None:
    _atomic_write_json(DATA_DIR / filename, data)


def write_json_path(path: str | Path, data: Any) -> None:
    _atomic_write_json(Path(path), data)


def read_city_graph() -> dict[str, Any]:
    return read_json("city_graph.json")


def read_evacuation_zones() -> list[dict]:
    return read_json("evacuation_zones.json")


def read_safe_zones() -> list[dict]:
    return read_json("safe_zones.json")


def read_disaster_events() -> list[dict]:
    return read_json("disaster_events.json")


def write_disaster_events(events: list[dict]) -> None:
    write_json("disaster_events.json", events)


def read_rescue_units() -> list[dict]:
    return read_json("rescue_units.json")


def write_rescue_units(units: list[dict]) -> None:
    write_json("rescue_units.json", units)


def read_rescue_missions() -> list[dict[str, Any]]:
    path = DATA_DIR / "rescue_missions.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_rescue_missions(missions: list[dict[str, Any]]) -> None:
    write_json("rescue_missions.json", missions)


def read_rescue_log_rows() -> list[dict[str, str]]:
    path = DATA_DIR / "rescue_log.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def append_rescue_log_row(row: dict[str, Any]) -> None:
    path = DATA_DIR / "rescue_log.csv"
    fieldnames = [
        "log_id",
        "timestamp",
        "zone",
        "algorithm_used",
        "path",
        "total_cost",
        "people_evacuated",
        "rescue_unit",
        "status",
    ]
    rows = read_rescue_log_rows()
    rows.append({k: str(row.get(k, "")) for k in fieldnames})
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".csv")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_safe_zones(zones: list[dict]) -> None:
    write_json("safe_zones.json", zones)


def next_log_id() -> str:
    rows = read_rescue_log_rows()
    best = 0
    for r in rows:
        lid = r.get("log_id", "")
        if lid.startswith("LOG-"):
            try:
                best = max(best, int(lid.split("-", 1)[1]))
            except (IndexError, ValueError):
                pass
    return f"LOG-{best + 1:03d}"
