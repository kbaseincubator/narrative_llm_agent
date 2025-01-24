import networkx as nx
from pyvis.network import Network
import random
from pathlib import Path

# Load the GraphML file
G = nx.read_graphml(Path(__file__).parent.parent / "kbase_simple_llama31-32k-ctx_processed" / "graph_chunk_entity_relation.graphml")

# Create a Pyvis network
net = Network(height="100vh", notebook=True)

# Convert NetworkX graph to Pyvis network
net.from_nx(G)


# Add colors and title to nodes
for node in net.nodes:
    node["color"] = "#{:06x}".format(random.randint(0, 0xFFFFFF))
    if "description" in node:
        node["title"] = node["description"]

# Add title to edges
for edge in net.edges:
    if "description" in edge:
        edge["title"] = edge["description"]

# Save and display the network
net.show("knowledge_graph_processed.html")
