from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _ROOT / "data"
CITIES_DIR = DATA_DIR / "cities"
CITY_MAP = {
    "Veridian City": "veridian",
    "Harborfield": "harborfield",
    "Maplecrest": "maplecrest",
}


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=path.suffix or ".tmp")
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


def _atomic_write_json(path: Path, data: Any) -> None:
    content = json.dumps(data, indent=2, ensure_ascii=False)
    _atomic_write_text(path, content + "\n")


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _city_slug(city: str) -> str:
    return CITY_MAP.get(city, "veridian")


def _city_file(prefix: str, city: str) -> Path:
    return CITIES_DIR / f"{prefix}_{_city_slug(city)}.json"


def load_city_graph(city: str = "Veridian City") -> dict:
    return _read_json(_city_file("city", city))


def save_city_graph(data, city: str = "Veridian City") -> None:
    _atomic_write_json(_city_file("city", city), data)


def load_safe_zones(city: str = "Veridian City") -> list:
    return _read_json(_city_file("safe_zones", city))


def load_safe_zones_df(city: str = "Veridian City") -> pd.DataFrame:
    return pd.DataFrame(load_safe_zones(city))


def save_safe_zones(data, city: str = "Veridian City") -> None:
    _atomic_write_json(_city_file("safe_zones", city), data)


def load_disaster_events(city: str = "Veridian City") -> list:
    return _read_json(_city_file("events", city))


def load_disaster_events_df(city: str = "Veridian City") -> pd.DataFrame:
    return pd.DataFrame(load_disaster_events(city))


def save_disaster_events(data, city: str = "Veridian City") -> None:
    _atomic_write_json(_city_file("events", city), data)


def load_rescue_units(city: str = "Veridian City") -> list:
    return _read_json(_city_file("units", city))


def save_rescue_units(data, city: str = "Veridian City") -> None:
    _atomic_write_json(_city_file("units", city), data)


def load_rescue_units_df(city: str = "Veridian City") -> pd.DataFrame:
    return pd.DataFrame(load_rescue_units(city))


def load_resources() -> dict:
    return _read_json(DATA_DIR / "resources.json")


def save_resources(data) -> None:
    _atomic_write_json(DATA_DIR / "resources.json", data)


def load_evacuation_zones(city: str = "Veridian City") -> list:
    return _read_json(_city_file("zones", city))

def load_evacuation_zones_df(city: str = "Veridian City") -> pd.DataFrame:
    return pd.DataFrame(load_evacuation_zones(city))


RESCUE_LOG_COLUMNS = [
    "log_id",
    "timestamp",
    "city",
    "team_id",
    "team_name",
    "team_type",
    "from_node",
    "from_name",
    "to_node",
    "to_name",
    "algorithm_used",
    "path_length",
    "nodes_explored",
    "time_ms",
    "people_rescued",
    "fuel_used",
    "medical_kits_used",
    "knapsack_selected",
    "status",
]


def load_rescue_log_df() -> pd.DataFrame:
    path = DATA_DIR / "rescue_log.csv"
    if not path.exists():
        return pd.DataFrame(columns=RESCUE_LOG_COLUMNS)
    df = pd.read_csv(path)
    for col in RESCUE_LOG_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[RESCUE_LOG_COLUMNS]


def save_rescue_log_df(df: pd.DataFrame) -> None:
    path = DATA_DIR / "rescue_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    for col in RESCUE_LOG_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".csv")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            df[RESCUE_LOG_COLUMNS].to_csv(f, index=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def append_rescue_log(row: dict[str, Any]) -> None:
    df = load_rescue_log_df()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_rescue_log_df(df)


def reset_resource_runtime_state() -> None:
    resources = load_resources()
    for item in resources.get("inventory", []):
        item["distributed"] = 0
        item["in_transit"] = 0
    resources["safe_zone_allocations"] = []
    resources["distribution_log"] = []
    save_resources(resources)

    for city in CITY_MAP.keys():
        zones = load_safe_zones(city)
        for zone in zones:
            zone["current_occupancy"] = 0
            zone["resources"] = {
                "food_packets": 0,
                "water_liters": 0,
                "medical_kits": 0,
                "blankets": 0,
                "rescue_boats": 0,
                "emergency_medicines": 0,
            }
            zone["victims"] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "recovered": 0, "total": 0}
        save_safe_zones(zones, city)

