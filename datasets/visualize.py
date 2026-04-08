import networkx as nx
import matplotlib.pyplot as plt
from data import nodes, edges, node_types, rescuers

G = nx.Graph()

# -------------------------------
# ADD NODES WITH POSITIONS
# -------------------------------
for node, (x, y) in nodes.items():
    G.add_node(node, pos=(x, y))

# -------------------------------
# ADD EDGES
# -------------------------------
for node in edges:
    for neighbor, _ in edges[node]:
        G.add_edge(node, neighbor)

# -------------------------------
# GET POSITIONS
# -------------------------------
pos = nx.get_node_attributes(G, 'pos')

# -------------------------------
# NODE COLORING
# -------------------------------
color_map = []

for node in G.nodes():
    if node_types.get(node) == 'hospital':
        color_map.append('red')
    elif node_types.get(node) == 'safe_zone':
        color_map.append('green')
    elif node_types.get(node) == 'residential':
        color_map.append('orange')
    else:
        color_map.append('lightblue')  # junction

# -------------------------------
# DRAW GRAPH (NODES + EDGES)
# -------------------------------
nx.draw(G, pos, node_color=color_map, with_labels=True, node_size=600)

# -------------------------------
# RESCUER LABELS (OFFSET TO AVOID OVERLAP)
# -------------------------------
labels = {}

for r in rescuers:
    node = r['location']
    if node in labels:
        labels[node].append(r['id'])
    else:
        labels[node] = [r['id']]

# Create offset positions
offset_pos = {}

for node, (x, y) in pos.items():
    if node in labels:
        # Spread multiple rescuers around node
        for i, rid in enumerate(labels[node]):
            angle = i * 0.8  # spacing
            dx = 0.4 * (i + 1)
            dy = 0.3 * (i + 1)

            offset_pos[(node, rid)] = (x + dx, y + dy)
    else:
        offset_pos[(node, "")] = (x, y)

# Draw each rescuer label separately
for node in labels:
    x, y = pos[node]
    for i, rid in enumerate(labels[node]):
        plt.text(
            x + 0.4*(i+1),
            y + 0.3*(i+1),
            rid,
            fontsize=9,
            color='black',
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none')
        )

# just for demo
path = ['F', 'G', 'K', 'O', 'S', 'T'] 

# -------------------------------
# HIGHLIGHT PATH
# -------------------------------

path_edges = list(zip(path, path[1:]))

nx.draw_networkx_edges(
    G,
    pos,
    edgelist=path_edges,
    edge_color='red',
    width=3
)

# -------------------------------
# TITLE
# -------------------------------
plt.title("City Graph with Rescuers")

# -------------------------------
# SHOW
# -------------------------------
plt.show()