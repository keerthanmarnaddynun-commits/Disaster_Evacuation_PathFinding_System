from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from algorithms.dijkstra import dijkstra
from core.data_loader import load_city_graph, load_disaster_events, load_safe_zones, save_disaster_events
from core.graph_engine import load_graph, get_adjacency_list, get_edge_distance_km
from core.knapsack import knapsack_supply
from core.resource_manager import ResourceManager


def _progress_color(frac: float) -> str:
    if frac < 0.2:
        return "#bf616a"
    if frac < 0.5:
        return "#ebcb8b"
    return "#8fbcbb"


def render():
    active_city = st.session_state.get("active_city", "Veridian City")
    rm = ResourceManager()
    data = rm.load()
    inv_df = rm.get_inventory()
    inv = inv_df.to_dict(orient="records")
    summary = rm.get_hub_summary()
    safe_zones = load_safe_zones(active_city)
    city_graph = load_city_graph(active_city)
    node_zone_map = {n["id"]: n.get("zone", "Zone-X") for n in city_graph.get("nodes", [])}

    hub = data.get("hub", {})
    st.markdown(f'<div style="font-size:2rem;font-weight:700;color:#eceff4;">Central Resource Hub - {active_city}</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div style='color:#d8dee9;'>{hub.get('name','')} • {hub.get('location','')}</div>",
        unsafe_allow_html=True,
    )

    # STATS ROW
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Available", int(summary["total_available"]))
    c2.metric("Total Distributed", int(summary["total_distributed"]))
    c3.metric("In Transit", int(summary["in_transit"]))
    c4.metric("Zones Supplied", int(summary["zones_supplied"]))
    c5.metric("Low Stock", len(summary["low_stock_alerts"]))

    # SECTION 1 — Inventory
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#88c0d0;">Inventory</div>', unsafe_allow_html=True)
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
                    <div style="font-weight:700;color:#eceff4;">{item.get('name')}</div>
                    <div>{low_badge}</div>
                  </div>
                  <div style="margin-top:10px;color:#d8dee9;">Available: <b style="color:#eceff4;">{avail}</b> {item.get('unit')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(min(1.0, max(0.0, frac)), text=f"Distributed {dist}/{total}")
            st.markdown(
                f"<div style='color:#d8dee9;margin-top:6px;'>In Transit: <b style='color:#eceff4;'>{transit}</b> &nbsp;|&nbsp; Distributed: <b style='color:#eceff4;'>{dist}</b></div>",
                unsafe_allow_html=True,
            )

    # SECTION 2 — Dispatch Resources
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#88c0d0;">Dispatch Resources</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    with st.form("dispatch_form"):
        st.markdown('<div style="font-weight:700;color:#eceff4;">Dispatch Resources to Safe Zone</div>', unsafe_allow_html=True)

        res_labels = {i["resource_id"]: f'{i["name"]} (avail: {int(i["available"])})' for i in inv}
        rid = st.selectbox("Select Resource", list(res_labels.keys()), format_func=lambda x: res_labels[x])

        sz_labels = {
            sz["id"]: f'{sz.get("node_id", "")} — {int(sz.get("current_occupancy",0))}/{int(sz.get("capacity",0))}'
            for sz in safe_zones
        }
        sz_id = st.selectbox("Select Safe Zone", list(sz_labels.keys()), format_func=lambda x: sz_labels[x])

        avail = int(next(i for i in inv if i["resource_id"] == rid)["available"])
        qty = st.number_input("Quantity", min_value=0, max_value=max(0, avail), value=min(50, max(0, avail)), step=10)
        do = st.form_submit_button("Dispatch", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if do and qty > 0:
        sz = next(z for z in safe_zones if z["id"] == sz_id)
        alloc = rm.distribute(rid, int(qty), sz_id, sz["name"], city=active_city)
        st.toast("Dispatched shipment.")

        # Show route from hub to safe zone via Dijkstra
        city = city_graph
        G = load_graph(city)
        adj = get_adjacency_list(G, mode="fastest", disaster_events=[], positions=None)
        hub_node = data.get("hub", {}).get("node_id", "N001")
        path, cost = dijkstra(adj, hub_node, sz["node_id"])
        if path:
            dist_km = sum(get_edge_distance_km(G, path[i], path[i + 1]) for i in range(len(path) - 1))
            st.info(f"Route from Hub to {sz['node_id']}: {' - '.join(path)} ({dist_km:.1f} km, ~{cost:.0f} min)")
        else:
            st.warning("No route found from hub to safe zone.")

    # SECTION 3 — Active Shipments
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#88c0d0;">Active Shipments</div>', unsafe_allow_html=True)
    live = rm.load()
    allocs = [a for a in live.get("safe_zone_allocations", []) if a.get("status") == "in_transit"]
    if not allocs:
        st.markdown('<div class="card" style="color:#d8dee9;">No shipments in transit</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="card" style="padding:0;">', unsafe_allow_html=True)
        for i, a in enumerate(allocs):
            cols = st.columns([0.22, 0.1, 0.26, 0.2, 0.12, 0.1])
            cols[0].markdown(f"<div style='padding:10px;color:#eceff4;'><b>{a.get('resource_name','')}</b></div>", unsafe_allow_html=True)
            cols[1].markdown(f"<div style='padding:10px;color:#d8dee9;'>{int(a.get('quantity',0))}</div>", unsafe_allow_html=True)
            cols[2].markdown(f"<div style='padding:10px;color:#d8dee9;'>{a.get('safe_zone_name','')}</div>", unsafe_allow_html=True)
            cols[3].markdown(f"<div style='padding:10px;color:#d8dee9;'>{a.get('dispatched_at','')}</div>", unsafe_allow_html=True)
            cols[4].markdown("<div style='padding:10px;'><span class='badge-blue'>in_transit</span></div>", unsafe_allow_html=True)
            if cols[5].button("Mark Delivered", key=f"del_{a.get('allocation_id')}"):
                rm.confirm_delivery(a.get("allocation_id"))
                rm.apply_recovery_cycle(active_city)
                st.toast("Shipment marked delivered.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # SECTION 4 — Safe Zone Inventory Status
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#88c0d0;">Safe Zone Inventory Status</div>', unsafe_allow_html=True)
    if st.button("Run Recovery Cycle", use_container_width=True):
        rec = rm.apply_recovery_cycle(active_city)
        st.success(f"Recovery updated: {rec['recovered']} civilians recovered in this cycle.")
        st.rerun()
    live = rm.load()
    all_allocs = live.get("safe_zone_allocations", [])
    for sz in load_safe_zones(active_city):
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
            st.dataframe(table, use_container_width=True, hide_index=True)

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
            st.dataframe(vdf, use_container_width=True, hide_index=True)

            needs = [r["resource"] for r in table if r["delivered"] == 0 and r["in_transit"] == 0]
            if needs:
                st.markdown(f"<div style='color:#d8dee9;'><b>Needs Assessment:</b> {', '.join(needs)}</div>", unsafe_allow_html=True)

    all_zones = load_safe_zones(active_city)
    total_injured = 0
    total_recovered = 0
    for z in all_zones:
        victims = z.get("victims", {})
        total_injured += int(victims.get("critical", 0)) + int(victims.get("high", 0)) + int(victims.get("medium", 0)) + int(victims.get("low", 0))
        total_recovered += int(victims.get("recovered", 0))
    st.subheader("Victim Recovery Status")
    c1, c2 = st.columns(2)
    c1.metric("Still Injured", total_injured)
    c2.metric("Recovered", total_recovered)
    if total_injured == 0 and total_recovered > 0:
        st.success("Disaster response successful: all rescued victims at safe zones are now recovered.")
        active_events = load_disaster_events(active_city)
        if any(e.get("active", False) for e in active_events):
            if st.button("Settle Disaster Events for this Map"):
                for e in active_events:
                    if e.get("active", False):
                        e["active"] = False
                        e["resolved_at"] = datetime.now().isoformat(timespec="seconds")
                save_disaster_events(active_events, active_city)
                st.rerun()

    # SECTION 5 — Distribution Log
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#88c0d0;">Distribution Log</div>', unsafe_allow_html=True)
    log = rm.get_distribution_log(limit=50)
    st.dataframe(log, use_container_width=True, hide_index=True)

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
    st.dataframe(pd.DataFrame(resources), use_container_width=True)
    if st.button("Optimize Supply Allocation"):
        out = knapsack_supply(resources, budget=min(100, budget))
        st.dataframe(pd.DataFrame(out["selected"]), use_container_width=True)
        st.dataframe(pd.DataFrame(out["dp_table"]).style.background_gradient(cmap="Blues"), use_container_width=True)

    # SECTION 6 — Restock Hub
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#88c0d0;">Restock Hub</div>', unsafe_allow_html=True)
    with st.form("restock_form"):
        rid2 = st.selectbox("Select resource", [i["resource_id"] for i in inv], format_func=lambda x: next(i["name"] for i in inv if i["resource_id"] == x))
        qty2 = st.number_input("Quantity", min_value=0, value=100, step=50)
        reason = st.text_input("Reason", value=f"Restock @ {datetime.now().strftime('%H:%M')}")
        ok = st.form_submit_button("Restock", use_container_width=True)
    if ok and qty2 > 0:
        rm.restock(rid2, int(qty2), reason)
        st.toast("Hub restocked.")
        st.rerun()

