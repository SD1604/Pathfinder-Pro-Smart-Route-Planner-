import os
import osmnx as ox
import networkx as nx

# def initialize_graph(area_name="Delhi, India"):

#     print(f"Initialising graph for {area_name}")

#     graph = ox.graph_from_place(area_name, network_type="drive")

#     nodes_count = len(graph.nodes)
#     egdes_count = len(graph.edges)

#     print("Graph initialized successfully!")
#     print(f"Number of nodes: {nodes_count}")
#     print(f"Number of egdes: {egdes_count}")

#     return graph

def initialize_graph(file_path="delhi_full.graphml"):
    # Check if we already have the map saved on our computer
    if os.path.exists(file_path):
        print(f"Loading graph from local file: {file_path}")
        return ox.load_graphml(file_path)

    print("File not found. Downloading Delhi graph from the internet...")
    
    # 1
    # (left, bottom, right, top)
    delhi_bbox = (76.83, 28.40, 77.35, 28.89)
    G = ox.graph_from_bbox(bbox=delhi_bbox, network_type='drive', retain_all=False)

    # 2. Filter for SCC (This fixes the "broken route" problem)
    largest_scc_nodes = max(nx.strongly_connected_components(G), key=len)
    G = G.subgraph(largest_scc_nodes).copy()

    # 3. Save it so we never have to download it again!
    print(f"Saving graph to {file_path} for next time...")
    ox.save_graphml(G, filepath=file_path)

    print(f"Graph loaded with {len(G.nodes)} nodes and {len(G.edges)} edges.")
    return G


if __name__ == "__main__":
    
    G = initialize_graph("Delhi, India")

    ox.plot_graph(G)