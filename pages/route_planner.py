"""Evacuation route planner UI — automatic algorithm selection."""

from __future__ import annotations

import streamlit as st

from core import data_loader
from core.algorithm_selector import AlgorithmSelector
from utils import visualizer
from utils import app_state


def render() -> None:
    st.header("Evacuation Route Planner")
    G = app_state.get_city_graph()
    events = data_loader.read_disaster_events()
    nodes = sorted(G.nodes())
    safe_rows = data_loader.read_safe_zones()
    safe_node_by_label = {f"{r['name']} ({r['node_id']})": r["node_id"] for r in safe_rows}

    col1, col2 = st.columns(2)
    with col1:
        start = st.selectbox("Start node", nodes, index=0)
    with col2:
        goal_label = st.selectbox(
            "Goal / safe zone",
            list(safe_node_by_label.keys()),
            index=0,
        )
    goal = safe_node_by_label[goal_label]

    if st.button("Find Best Evacuation Route", type="primary"):
        with st.spinner("Analyzing scenario and running candidate algorithms…"):
            out = AlgorithmSelector.select_and_run(
                G,
                start,
                goal,
                events,
                rescue_context={},
            )

        rec = out.get("recommended", {})
        path = rec.get("path")
        conf = out.get("scenario_analysis", {}).get("recommendation_confidence", "medium")
        badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "🟡")

        st.markdown(f"**Confidence:** {badge} `{conf.upper()}`")

        if path:
            meta = {n["id"]: n for n in data_loader.read_city_graph().get("nodes", [])}
            steps = " → ".join(f"{p} ({meta.get(p, {}).get('name', p)})" for p in path)
            st.success(
                f"**{rec.get('algorithm', '?')}** ({rec.get('mode', '')}) — "
                f"composite: {rec.get('composite_score', 0):.4f} | "
                f"est. time: {rec.get('estimated_time_min', 0):.2f} min | "
                f"safety: {rec.get('safety_score', 0):.1f} | "
                f"compute: {rec.get('ran_in_ms', 0):.2f} ms"
            )
            fig = visualizer.render_city_graph(G, highlighted_path=path, title="Recommended route")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"**Path:** {steps}")
        else:
            st.warning("No viable route found under current disaster conditions.")

        with st.expander("Why this route?", expanded=True):
            st.markdown(rec.get("why_selected", "_No justification available._"))
            sa = out.get("scenario_analysis", {})
            st.subheader("Scenario analysis")
            st.table(
                {
                    "disaster_pressure": [f"{float(sa.get('disaster_pressure', 0)):.4f}"],
                    "graph_density": [f"{float(sa.get('graph_density', 0)):.6f}"],
                    "recommendation_confidence": [sa.get("recommendation_confidence", "")],
                }
            )
            st.caption("Critical nodes and bridges refer to the default shortest path probe.")
            st.write("**Critical nodes (risk > 0.7) on probe path:**", sa.get("critical_nodes_on_path", []))
            st.write("**Bridge nodes on probe path:**", sa.get("bridge_nodes_on_path", []))

        with st.expander("Alternative routes (runners-up)", expanded=False):
            for alt in out.get("alternatives", []):
                st.write(
                    f"- **{alt.get('algorithm')}** ({alt.get('mode')}) — "
                    f"composite {alt.get('composite_score', 0):.4f} — "
                    f"path: `{alt.get('path')}`"
                )

        with st.expander("All algorithm results", expanded=False):
            rows = []
            for r in out.get("all_results", []):
                rows.append(
                    {
                        "algorithm": r.get("algorithm"),
                        "mode": r.get("mode"),
                        "cost": r.get("weighted_cost"),
                        "estimated_time_min": r.get("estimated_time_min"),
                        "safety_score": r.get("safety_score"),
                        "ran_in_ms": r.get("ran_in_ms"),
                        "timed_out": r.get("timed_out"),
                    }
                )
            st.dataframe(rows, use_container_width=True)


if __name__ == "__main__":
    render()
