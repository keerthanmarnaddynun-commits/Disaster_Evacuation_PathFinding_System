from __future__ import annotations

from datetime import datetime
import uuid

import pandas as pd

from core.data_loader import load_resources, load_safe_zones, save_resources, save_safe_zones


class ResourceManager:
    """
    Manages distribution of resources from Central Hub to safe zones.
    All state in data/resources.json.
    Admin (user) manually dispatches resources by reviewing safe zone needs.
    """

    def load(self) -> dict:
        return load_resources()

    def save(self, data) -> None:
        save_resources(data)

    def get_inventory(self) -> pd.DataFrame:
        data = self.load()
        out = []
        for item in data.get("inventory", []):
            total = int(item.get("total_stock", 0))
            distributed = int(item.get("distributed", 0))
            in_transit = int(item.get("in_transit", 0))
            available = max(0, total - distributed - in_transit)
            out.append({**item, "available": available})
        return pd.DataFrame(out)

    def distribute(self, resource_id, quantity, safe_zone_id, safe_zone_name) -> dict:
        data = self.load()
        qty = int(quantity)
        if qty <= 0:
            raise ValueError("Quantity must be > 0")

        inv = data.get("inventory", [])
        item = next((i for i in inv if i.get("resource_id") == resource_id), None)
        if not item:
            raise ValueError("Unknown resource_id")

        total = int(item.get("total_stock", 0))
        distributed = int(item.get("distributed", 0))
        in_transit = int(item.get("in_transit", 0))
        available = total - distributed - in_transit
        if qty > available:
            raise ValueError("Insufficient available stock")

        item["in_transit"] = int(item.get("in_transit", 0)) + qty

        allocation_id = f"ALC-{uuid.uuid4().hex[:8].upper()}"
        allocation = {
            "allocation_id": allocation_id,
            "resource_id": resource_id,
            "resource_name": item.get("name", ""),
            "quantity": qty,
            "unit": item.get("unit", ""),
            "safe_zone_id": safe_zone_id,
            "safe_zone_name": safe_zone_name,
            "status": "in_transit",
            "dispatched_at": datetime.now().isoformat(timespec="seconds"),
        }
        data.setdefault("safe_zone_allocations", []).append(allocation)

        data.setdefault("distribution_log", []).append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": "dispatch",
                "resource_id": resource_id,
                "resource_name": item.get("name", ""),
                "quantity": qty,
                "safe_zone_id": safe_zone_id,
                "safe_zone_name": safe_zone_name,
            }
        )

        self.save(data)
        return allocation

    def confirm_delivery(self, allocation_id):
        data = self.load()
        allocs = data.get("safe_zone_allocations", [])
        alloc = next((a for a in allocs if a.get("allocation_id") == allocation_id), None)
        if not alloc:
            raise ValueError("Unknown allocation_id")
        if alloc.get("status") == "delivered":
            return

        resource_id = alloc["resource_id"]
        qty = int(alloc.get("quantity", 0))

        # Update inventory in resources.json: move in_transit -> distributed
        inv = data.get("inventory", [])
        item = next((i for i in inv if i.get("resource_id") == resource_id), None)
        if not item:
            raise ValueError("Unknown resource in allocation")
        item["in_transit"] = max(0, int(item.get("in_transit", 0)) - qty)
        item["distributed"] = int(item.get("distributed", 0)) + qty

        alloc["status"] = "delivered"
        alloc["delivered_at"] = datetime.now().isoformat(timespec="seconds")

        data.setdefault("distribution_log", []).append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": "delivered",
                "resource_id": resource_id,
                "resource_name": item.get("name", ""),
                "quantity": qty,
                "safe_zone_id": alloc.get("safe_zone_id", ""),
                "safe_zone_name": alloc.get("safe_zone_name", ""),
            }
        )

        self.save(data)

        # Update safe_zones.json resources dict for that zone
        zones = load_safe_zones()
        sz = next((z for z in zones if z.get("id") == alloc.get("safe_zone_id")), None)
        if sz:
            key_map = {
                "R001": "food_packets",
                "R002": "water_liters",
                "R003": "medical_kits",
                "R004": "blankets",
                "R005": "rescue_boats",
                "R006": "emergency_medicines",
            }
            k = key_map.get(resource_id)
            if k:
                sz.setdefault("resources", {})
                sz["resources"][k] = int(sz["resources"].get(k, 0)) + qty
            save_safe_zones(zones)

    def restock(self, resource_id, quantity, reason):
        data = self.load()
        qty = int(quantity)
        if qty <= 0:
            raise ValueError("Quantity must be > 0")
        inv = data.get("inventory", [])
        item = next((i for i in inv if i.get("resource_id") == resource_id), None)
        if not item:
            raise ValueError("Unknown resource_id")

        item["total_stock"] = int(item.get("total_stock", 0)) + qty
        data.setdefault("distribution_log", []).append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": "restock",
                "resource_id": resource_id,
                "resource_name": item.get("name", ""),
                "quantity": qty,
                "safe_zone_id": "",
                "safe_zone_name": "",
                "reason": str(reason or ""),
            }
        )
        self.save(data)

    def get_safe_zone_inventory(self, safe_zone_id) -> pd.DataFrame:
        data = self.load()
        alloc_df = pd.DataFrame(data.get("safe_zone_allocations", []))
        if alloc_df.empty:
            return pd.DataFrame(columns=["resource_id", "quantity"])
        filt = alloc_df[(alloc_df["safe_zone_id"] == safe_zone_id) & (alloc_df["status"] == "delivered")]
        return filt.groupby("resource_id", as_index=False)["quantity"].sum()

    def get_distribution_log(self, limit=50) -> pd.DataFrame:
        data = self.load()
        log_df = pd.DataFrame(data.get("distribution_log", []))
        if log_df.empty:
            return pd.DataFrame()
        return log_df.iloc[::-1].head(int(limit))

    def get_hub_summary(self) -> dict:
        inv = self.get_inventory().to_dict(orient="records")
        total_available = sum(int(i.get("available", 0)) for i in inv)
        total_distributed = sum(int(i.get("distributed", 0)) for i in inv)
        in_transit = sum(int(i.get("in_transit", 0)) for i in inv)
        data = self.load()
        zones_supplied = len({a.get("safe_zone_id") for a in data.get("safe_zone_allocations", []) if a.get("status") == "delivered"})
        low_stock_alerts = [i for i in inv if int(i.get("total_stock", 0)) > 0 and (int(i.get("available", 0)) / int(i.get("total_stock", 1))) < 0.1]
        return {
            "total_available": total_available,
            "total_distributed": total_distributed,
            "in_transit": in_transit,
            "zones_supplied": zones_supplied,
            "low_stock_alerts": low_stock_alerts,
        }