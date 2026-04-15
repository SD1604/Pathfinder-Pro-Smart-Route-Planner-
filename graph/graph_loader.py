import os
import osmnx as ox
import networkx as nx
import requests


# def initialize_graph(area_name="Delhi, India"):

#     print(f"Initialising graph for {area_name}")

#     graph = ox.graph_from_place(area_name, network_type="drive")

#     nodes_count = len(graph.nodes)
#     egdes_count = len(graph.edges)

#     print("Graph initialized successfully!")
#     print(f"Number of nodes: {nodes_count}")
#     print(f"Number of egdes: {egdes_count}")

#     return graph

GDRIVE_FILE_ID = "1IluMTiHX1vJVismcXdIUsZzV5m9GD3u3"
GRAPHML_PATH = "delhi_full.graphml"

def download_from_gdrive(file_id, destination):
    print("Downloading delhi_full.graphml from Google Drive...")
    URL = "https://drive.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={"id": file_id}, stream=True)
    
    # Handle large file confirmation token
    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
            break

    if token:
        response = session.get(URL, params={"id": file_id, "confirm": token}, stream=True)

    with open(destination, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)
    print("Download complete!")


def initialize_graph(file_path=GRAPHML_PATH):
    if not os.path.exists(file_path):
        download_from_gdrive(GDRIVE_FILE_ID, file_path)

    print(f"Loading graph from {file_path}...")
    G = ox.load_graphml(file_path)
    print(f"Graph loaded with {len(G.nodes)} nodes and {len(G.edges)} edges.")
    return G