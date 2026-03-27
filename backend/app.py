import time
from flask import Flask, request, jsonify
from flask_cors import CORS # pyright: ignore[reportMissingModuleSource]
import osmnx as ox
from algorithms.dijkstra import custom_dijkstra
from algorithms.astar_path import astar_path
from scipy.spatial import KDTree
import pandas as pd
from graph.graph_loader import initialize_graph
from utils.geo_utils import get_nearest_node, build_spatial_index

app = Flask(__name__)
CORS(app) 

# 1. Load the graph
print("Loading map data... please wait.")
# G = initialize_graph()

G = ox.load_graphml("delhi_full.graphml")

print("Imputing Road Speeds and Travel Times...")
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)

tree, node_ids = build_spatial_index(G)

# PRE-CACHing the coordinates for instant lookup
node_coords = {node: [data['y'], data['x']] for node, data in G.nodes(data=True)}
print("Map and Cache loaded successfully!")

@app.route('/find_path', methods=['POST'])
def find_path():
    data = request.json

    start_coords = (data['start'][0], data['start'][1])
    end_coords = (data['end'][0], data['end'][1])

    # --- UI SYNC: START BENCHMARK ---
    ui_bench_start = time.time()
    # -------------------------------

    start_node = get_nearest_node(tree, node_ids, start_coords[0], start_coords[1])
    end_node = get_nearest_node(tree, node_ids, end_coords[0], end_coords[1])
    # print(f"Nearest nodes found in: {time.time() - t1:.4f}s")

    # 3. A* Pathfinding
    # t2 = time.time()
    path_nodes, total_time_seconds, nodes_visited = astar_path(G, start_node, end_node, weight='travel_time')
    # print(f"A* search took: {time.time() - t2:.4f}s")
    
    # --- UI SYNC: END BENCHMARK ---
    execution_time_ms = (time.time() - ui_bench_start) * 1000
    # -----------------------------

    if not path_nodes:
        return jsonify({"error": "No path found"}), 404

    time_minutes = total_time_seconds/60
    
    # 4. Calculate Time and convert to kilometers and assume 30 km/h average Delhi traffic speed
    distance_meters = sum(
    G.get_edge_data(u, v)[0].get('length', 0) 
    for u, v in zip(path_nodes[:-1], path_nodes[1:]))
    distance_km = distance_meters / 1000

    # 4. Convert Node IDs to Lat/Lng using FAST cache
    route_coordinates = [node_coords[node] for node in path_nodes]
        
    return jsonify({
        "path": route_coordinates,
        "distance": round(distance_km, 2),
        "time": round(time_minutes, 1),
        # ADDED FOR COBALT UI:
        "execution_time": round(execution_time_ms, 2),
        "nodes_visited": nodes_visited
    })

if __name__ == '__main__':
    app.run(port=5000, debug=True)