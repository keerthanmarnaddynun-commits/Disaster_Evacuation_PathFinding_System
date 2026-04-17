from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from algorithms.dijkstra import dijkstra
from core.data_loader import load_city_graph, load_disaster_events, load_safe_zones, save_disaster_events, load_rescue_log_df
from core.graph_engine import load_graph, get_adjacency_list, get_edge_distance_km
from core.knapsack import knapsack_supply
from core.resource_manager import ResourceManager


def _progress_color(frac: float) -> str:
    if frac < 0.2:
        return "#ed8796"
    if frac < 0.5:
        return "#eed49f"
    return "#a6da95"


def render():
    active_map = st.session_state.get("active_map", "Map 1")
    st.session_state["active_city"] = active_map
    rm = ResourceManager()
    data = rm.load()
    inv_df = rm.get_inventory()
    inv = inv_df.to_dict(orient="records")
    summary = rm.get_hub_summary()
    safe_zones = load_safe_zones(active_map)
    city_graph = load_city_graph(active_map)
    events = load_disaster_events(active_map)
    node_zone_map = {n["id"]: n.get("zone", "Zone-X") for n in city_graph.get("nodes", [])}

    hub = data.get("hub", {})
    st.markdown(f'<div style="font-size:2rem;font-weight:700;color:#cad3f5;">Central Resource Hub - {active_map}</div>', unsafe_allow_html=True)
    st.caption(f"Active map: {active_map}")
    st.markdown(
        f"<div style='color:#b8c0e0;'>{hub.get('name','')} • {hub.get('location','')}</div>",
        unsafe_allow_html=True,
    )

    # Calculate rescue statistics for consistent application state
    rescue_log = load_rescue_log_df()
    city_rescue_log = rescue_log[rescue_log["city"] == active_map] if not rescue_log.empty else rescue_log
    total_people_rescued_all_time = int(city_rescue_log["people_rescued"].fillna(0).sum()) if not city_rescue_log.empty else 0

    # Count stranded people in city (from city graph nodes)
    total_stranded = sum(int(n.get("people_stranded", 0)) for n in city_graph.get("nodes", []))

    # Count people in safe zones
    total_in_safe_zones = sum(int(z.get("current_occupancy", 0)) for z in safe_zones)

    # STATS ROW - Rescue focused metrics
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Rescue Overview</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("People Stranded", total_stranded)
    c2.metric("Rescued (All Time)", total_people_rescued_all_time)
    c3.metric("In Safe Zones", total_in_safe_zones)
    c4.metric("Active Disasters", len([e for e in events if e.get("active", False)]))

    # Resource Hub Stats
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;margin-top:1rem;">Resource Hub Status</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Available", int(summary["total_available"]))
    c2.metric("Total Distributed", int(summary["total_distributed"]))
    c3.metric("In Transit", int(summary["in_transit"]))
    c4.metric("Zones Supplied", int(summary["zones_supplied"]))
    c5.metric("Low Stock", len(summary["low_stock_alerts"]))

    # SECTION 1 — Inventory
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Inventory</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, item in enumerate(inv):
        with cols[i % 3]:
            total = int(item.get("total_stock", 0))
            dist = int(item.get("distributed", 0))
            transit = int(item.get("in_transit", 0))
            avail = int(item.get("available", 0))
            frac = (dist / total) if total else 0.0
            color = _progress_color(frac)
            low = total > 0 and (avail / total) < 0.1
            low_badge = '<span class="badge-red">LOW</span>' if low else ""
            st.markdown(
                f"""
                <div class="card">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-weight:700;color:#cad3f5;">{item.get('name')}</div>
                    <div>{low_badge}</div>
                  </div>
                  <div style="margin-top:10px;color:#b8c0e0;">Available: <b style="color:#cad3f5;">{avail}</b> {item.get('unit')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(min(1.0, max(0.0, frac)), text=f"Distributed {dist}/{total}")
            st.markdown(
                f"<div style='color:#b8c0e0;margin-top:6px;'>In Transit: <b style='color:#cad3f5;'>{transit}</b> &nbsp;|&nbsp; Distributed: <b style='color:#cad3f5;'>{dist}</b></div>",
                unsafe_allow_html=True,
            )

    # SECTION 2 — Dispatch Resources
    st.markdown('<div style="height:50px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Dispatch Resources</div>', unsafe_allow_html=True)
    with st.form("dispatch_form"):
        st.markdown('<div style="font-weight:700;color:#cad3f5;">Dispatch Resources to Safe Zone</div>', unsafe_allow_html=True)

        res_labels = {i["resource_id"]: f'{i["name"]} (avail: {int(i["available"])})' for i in inv}
        rid = st.selectbox("Select Resource", list(res_labels.keys()), format_func=lambda x: res_labels[x])

        sz_labels = {
            sz["id"]: f'{sz.get("node_id", "")} — {int(sz.get("current_occupancy",0))}/{int(sz.get("capacity",0))}'
            for sz in safe_zones
        }
        sz_id = st.selectbox("Select Safe Zone", list(sz_labels.keys()), format_func=lambda x: sz_labels[x])

        avail = int(next(i for i in inv if i["resource_id"] == rid)["available"])
        qty = st.number_input("Quantity", min_value=0, max_value=max(0, avail), value=min(50, max(0, avail)), step=10)
        do = st.form_submit_button("Dispatch", width="stretch")


    if do and qty > 0:
        sz = next(z for z in safe_zones if z["id"] == sz_id)
        alloc = rm.distribute(rid, int(qty), sz_id, sz["name"], city=active_map)
        st.toast("Dispatched shipment.")

        # Show route from hub to safe zone via Dijkstra
        city = city_graph
        G = load_graph(city)
        adj = get_adjacency_list(G, mode="fastest", disaster_events=[], positions=None)
        hub_node = next((z.get("node_id") for z in safe_zones if z.get("node_id")), city_graph.get("nodes", [{}])[0].get("id", ""))
        path, cost = dijkstra(adj, hub_node, sz["node_id"])
        if path:
            dist_km = sum(get_edge_distance_km(G, path[i], path[i + 1]) for i in range(len(path) - 1))
            st.info(f"Route from Hub to {sz['node_id']}: {' - '.join(path)} ({dist_km:.1f} km, ~{cost:.0f} min)")
        else:
            st.warning("No route found from hub to safe zone.")

    # SECTION 3 — Active Shipments
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Active Shipments</div>', unsafe_allow_html=True)
    live = rm.load()
    allocs = [a for a in live.get("safe_zone_allocations", []) if a.get("status") == "in_transit"]
    if not allocs:
        st.markdown('<div class="card" style="color:#b8c0e0;">No shipments in transit</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="card" style="padding:0;">', unsafe_allow_html=True)
        for i, a in enumerate(allocs):
            cols = st.columns([0.22, 0.1, 0.26, 0.2, 0.12, 0.1])
            cols[0].markdown(f"<div style='padding:10px;color:#cad3f5;'><b>{a.get('resource_name','')}</b></div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div style='padding:10px;color:#b8c0e0;'>{int(a.get('quantity',0))}</div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div style='padding:10px;color:#b8c0e0;'>{a.get('safe_zone_name','')}</div>", unsafe_allow_html=True)
            cols[3].markdown(f"<div style='padding:10px;color:#b8c0e0;'>{a.get('dispatched_at','')}</div>", unsafe_allow_html=True)
            cols[4].markdown("<div style='padding:10px;'><span class='badge-blue'>in_transit</span></div>", unsafe_allow_html=True)
            if cols[5].button("Mark Delivered", key=f"del_{a.get('allocation_id')}"):
                rm.confirm_delivery(a.get("allocation_id"), map_name=active_map)
                rm.apply_recovery_cycle(active_map)
                st.toast("Shipment marked delivered.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # SECTION 4 — Safe Zone Inventory Status
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Safe Zone Inventory Status</div>', unsafe_allow_html=True)
    if st.button("Run Recovery Cycle", width="stretch"):
        rec = rm.apply_recovery_cycle(active_map)
        st.success(f"Recovery updated: {rec['recovered']} civilians recovered in this cycle.")
        st.rerun()
    live = rm.load()
    all_allocs = live.get("safe_zone_allocations", [])
    for sz in load_safe_zones(active_map):
        node_label = sz.get("node_id", "")
        with st.expander(f"{node_label} — {int(sz.get('current_occupancy',0))}/{int(sz.get('capacity',0))}"):
            cap = int(sz.get("capacity", 1))
            cur = int(sz.get("current_occupancy", 0))
            st.progress(min(1.0, cur / cap) if cap else 0.0, text="Capacity usage")

            delivered = [a for a in all_allocs if a.get("safe_zone_id") == sz["id"] and a.get("status") == "delivered"]
            transit = [a for a in all_allocs if a.get("safe_zone_id") == sz["id"] and a.get("status") == "in_transit"]

            def sum_by_resource(items):
                out = {}
                for a in items:
                    out[a.get("resource_name", "")] = out.get(a.get("resource_name", ""), 0) + int(a.get("quantity", 0))
                return out

            del_map = sum_by_resource(delivered)
            tr_map = sum_by_resource(transit)

            table = []
            for item in inv:
                name = item.get("name", "")
                table.append({"resource": name, "delivered": del_map.get(name, 0), "in_transit": tr_map.get(name, 0)})
            st.dataframe(table, width="stretch", hide_index=True)

            victims = sz.get("victims", {"critical": 0, "high": 0, "medium": 0, "low": 0, "recovered": 0, "total": 0})
            vdf = pd.DataFrame(
                [
                    {"severity": "critical", "count": int(victims.get("critical", 0))},
                    {"severity": "high", "count": int(victims.get("high", 0))},
                    {"severity": "medium", "count": int(victims.get("medium", 0))},
                    {"severity": "low", "count": int(victims.get("low", 0))},
                    {"severity": "recovered", "count": int(victims.get("recovered", 0))},
                ]
            )
            st.dataframe(vdf, width="stretch", hide_index=True)

            # Resource Calculator: Calculate required resources to recover all victims
            critical_count = int(victims.get("critical", 0))
            high_count = int(victims.get("high", 0))
            medium_count = int(victims.get("medium", 0))
            low_count = int(victims.get("low", 0))
            total_injured = critical_count + high_count + medium_count + low_count

            if total_injured > 0:
                # Calculation logic: 1 food + 1 water per person per cycle
                # Medical kits: critical=4, high=3, medium=2, low=1 per person
                required_food = total_injured
                required_water = total_injured
                required_medical = (critical_count * 4) + (high_count * 3) + (medium_count * 2) + (low_count * 1)

                zone_resources = sz.get("resources", {})
                current_food = int(zone_resources.get("food_packets", 0))
                current_water = int(zone_resources.get("water_liters", 0))
                current_medical = int(zone_resources.get("medical_kits", 0))

                deficit_food = max(0, required_food - current_food)
                deficit_water = max(0, required_water - current_water)
                deficit_medical = max(0, required_medical - current_medical)

                st.markdown(
                    f"""<div style='color:#b8c0e0; margin-top:10px;'>
                    <b>Resource Requirements to Recover All Victims:</b><br/>
                    Food Packets: <b style="color:#a6da95;">{required_food}</b> (have: {current_food}, need: <b style="color:#{'ed8796' if deficit_food > 0 else 'a6da95'};">{deficit_food}</b>)<br/>
                    Water: <b style="color:#a6da95;">{required_water}</b> (have: {current_water}, need: <b style="color:#{'ed8796' if deficit_water > 0 else 'a6da95'};">{deficit_water}</b>)<br/>
                    Medical Kits: <b style="color:#a6da95;">{required_medical}</b> (have: {current_medical}, need: <b style="color:#{'ed8796' if deficit_medical > 0 else 'a6da95'};">{deficit_medical}</b>)
                    </div>""",
                    unsafe_allow_html=True,
                )

            needs = [r["resource"] for r in table if r["delivered"] == 0 and r["in_transit"] == 0]
            if needs:
                st.markdown(f"<div style='color:#b8c0e0;'><b>Needs Assessment:</b> {', '.join(needs)}</div>", unsafe_allow_html=True)

    # Calculate safe zone victim statistics only (people already rescued to safe zones)
    all_zones = load_safe_zones(active_map)
    total_injured_in_safe_zones = 0
    total_recovered_in_safe_zones = 0
    for z in all_zones:
        victims = z.get("victims", {})
        total_injured_in_safe_zones += int(victims.get("critical", 0)) + int(victims.get("high", 0)) + int(victims.get("medium", 0)) + int(victims.get("low", 0))
        total_recovered_in_safe_zones += int(victims.get("recovered", 0))

    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;margin-top:1rem;">Safe Zone Victim Recovery</div>', unsafe_allow_html=True)
    st.caption("Injury status of people already rescued and in safe zones")
    c1, c2, c3 = st.columns(3)
    c1.metric("Still Injured (Safe Zones)", total_injured_in_safe_zones)
    c2.metric("Recovered (Safe Zones)", total_recovered_in_safe_zones)
    c3.metric("Total in Safe Zones", total_in_safe_zones)
    if total_injured_in_safe_zones == 0 and total_recovered_in_safe_zones > 0:
        st.success("Disaster response successful: all rescued victims at safe zones are now recovered.")
        active_events = load_disaster_events(active_map)
        if any(e.get("active", False) for e in active_events):
            if st.button("Settle Disaster Events for this Map"):
                for e in active_events:
                    if e.get("active", False):
                        e["active"] = False
                        e["resolved_at"] = datetime.now().isoformat(timespec="seconds")
                save_disaster_events(active_events, active_map)
                st.rerun()

    # SECTION 5 — Distribution Log
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Distribution Log</div>', unsafe_allow_html=True)
    log = rm.get_distribution_log(limit=50)
    st.dataframe(log, width="stretch", hide_index=True)

    st.subheader("Optimal Supply Allocation")
    zone = st.selectbox("Select Safe Zone", [z["id"] for z in safe_zones], format_func=lambda x: next(z["name"] for z in safe_zones if z["id"] == x))
    budget = int(summary["total_available"])
    st.metric("Available capacity", budget)
    resources = []
    for item in inv:
        resources.append(
            {
                "resource_id": item["resource_id"],
                "name": item["name"],
                "value_per_unit": max(1, int(item["available"]) // 10 + 1),
                "cost_per_unit": 1,
                "max_available": int(item["available"]),
            }
        )
    st.dataframe(pd.DataFrame(resources), width="stretch")
    if st.button("Optimize Supply Allocation"):
        out = knapsack_supply(resources, budget=min(100, budget))
        st.dataframe(pd.DataFrame(out["selected"]), width="stretch")
        st.dataframe(pd.DataFrame(out["dp_table"]).style.background_gradient(cmap="Blues"), width="stretch")

    # SECTION 6 — Restock Hub
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#91d7e3;">Restock Hub</div>', unsafe_allow_html=True)
    with st.form("restock_form"):
        rid2 = st.selectbox("Select resource", [i["resource_id"] for i in inv], format_func=lambda x: next(i["name"] for i in inv if i["resource_id"] == x))
        qty2 = st.number_input("Quantity", min_value=0, value=100, step=50)
        reason = st.text_input("Reason", value=f"Restock @ {datetime.now().strftime('%H:%M')}")
        ok = st.form_submit_button("Restock", width="stretch")
    if ok and qty2 > 0:
        rm.restock(rid2, int(qty2), reason)
        st.toast("Hub restocked.")
        st.rerun()

