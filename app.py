import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import sys
import os

# Add the current directory to sys.path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datasets.data import nodes, edges, node_types, rescuers, requests, compute_edge_weight
from algorithms.Astar import astar, euclidean_distance
from algorithms.Dijkstra import dijkstra
from algorithms.bfs import bfs
from algorithms.dfs import dfs

# Page configuration
st.set_page_config(page_title="Disaster Evacuation & Rescue System", layout="wide")

st.title("🚑 Disaster Evacuation & Pathfinding System")
st.markdown("""
This system helps in finding the optimal paths for rescue operations during disasters. 
Select an algorithm and nodes to find the best route.
""")

# Helper to prepare graph for algorithms
def get_weighted_graph():
    weighted_graph = {}
    for node, neighbors in edges.items():
        weighted_graph[node] = []
        for neighbor, edge_data in neighbors:
            weight = compute_edge_weight(edge_data)
            weighted_graph[node].append((neighbor, weight))
    return weighted_graph

def get_unweighted_graph():
    unweighted_graph = {}
    for node, neighbors in edges.items():
        unweighted_graph[node] = [neighbor for neighbor, _ in neighbors]
    return unweighted_graph

# Sidebar for controls
st.sidebar.header("📍 Route Configuration")

all_nodes = sorted(list(nodes.keys()))
start_node = st.sidebar.selectbox("Select Start Node (Rescue Base/Rescuer)", all_nodes, index=all_nodes.index("F"))
end_node = st.sidebar.selectbox("Select End Node (Disaster Site/Safe Zone)", all_nodes, index=all_nodes.index("T"))

algorithm = st.sidebar.selectbox(
    "Select Pathfinding Algorithm",
    ["A*", "Dijkstra", "BFS", "DFS"]
)

st.sidebar.markdown("---")
st.sidebar.header("🏥 Node Legend")
st.sidebar.write("🔴 **Hospital**: Medical assistance")
st.sidebar.write("🟢 **Safe Zone**: Evacuation point")
st.sidebar.write("🟠 **Residential**: Disaster-prone area")
st.sidebar.write("🔵 **Junction**: Road intersection")

# Main Logic
if start_node == end_node:
    st.warning("Start and End nodes are the same!")
else:
    path = None
    cost = None

    if algorithm == "A*":
        weighted_graph = get_weighted_graph()
        path, cost = astar(weighted_graph, start_node, end_node, euclidean_distance, nodes)
    elif algorithm == "Dijkstra":
        weighted_graph = get_weighted_graph()
        path, cost = dijkstra(weighted_graph, start_node, end_node)
    elif algorithm == "BFS":
        unweighted_graph = get_unweighted_graph()
        path = bfs(unweighted_graph, start_node, end_node)
        cost = len(path) - 1 if path else float('inf')
    elif algorithm == "DFS":
        unweighted_graph = get_unweighted_graph()
        path = dfs(unweighted_graph, start_node, end_node)
        cost = len(path) - 1 if path else float('inf')

    # Layout with columns
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"🗺️ Map Visualization ({algorithm})")
        
        # Visualization logic
        fig, ax = plt.subplots(figsize=(10, 8))
        G = nx.Graph()

        # Add nodes with positions
        for node, (x, y) in nodes.items():
            G.add_node(node, pos=(x, y))

        # Add edges
        for node, neighbors in edges.items():
            for neighbor, _ in neighbors:
                G.add_edge(node, neighbor)

        pos = nx.get_node_attributes(G, 'pos')

        # Node coloring
        color_map = []
        for node in G.nodes():
            ntype = node_types.get(node)
            if ntype == 'hospital':
                color_map.append('red')
            elif ntype == 'safe_zone':
                color_map.append('green')
            elif ntype == 'residential':
                color_map.append('orange')
            else:
                color_map.append('skyblue')

        # Draw base graph
        nx.draw(G, pos, ax=ax, node_color=color_map, with_labels=True, 
                node_size=800, font_size=10, font_weight='bold', edge_color='gray', alpha=0.7)

        # Highlight path
        if path:
            path_edges = list(zip(path, path[1:]))
            nx.draw_networkx_edges(G, pos, edgelist=path_edges, edge_color='red', width=4, ax=ax)
            nx.draw_networkx_nodes(G, pos, nodelist=path, node_color='yellow', node_size=1000, ax=ax, alpha=0.5)

        st.pyplot(fig)

    with col2:
        st.subheader("📊 Path Details")
        if path:
            st.success(f"Path Found using {algorithm}!")
            st.write(f"**Route:** {' ➔ '.join(path)}")
            if algorithm in ["A*", "Dijkstra"]:
                st.write(f"**Total Travel Time:** {cost:.2f} hours")
            else:
                st.write(f"**Total Steps (Edges):** {cost}")
            
            st.markdown("---")
            st.subheader("🚑 Active Rescuers")
            for r in rescuers:
                if r['location'] in path:
                    st.info(f"**{r['id']}** ({r['vehicle_type']}) is on the path at node **{r['location']}**")
                else:
                    st.write(f"{r['id']} ({r['vehicle_type']}) at node {r['location']}")
        else:
            st.error("No path found between the selected nodes.")

st.markdown("---")
# Show Data Tables
with st.expander("📋 View Disaster Reports & Rescue Teams"):
    t1, t2 = st.tabs(["Rescue Requests", "Rescuer Teams"])
    with t1:
        st.table(requests)
    with t2:
        st.table(rescuers)
