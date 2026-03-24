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

tree, node_ids = build_spatial_index(G)

# PRE-CACHing the coordinates for instant lookup
node_coords = {node: [data['y'], data['x']] for node, data in G.nodes(data=True)}
print("Map and Cache loaded successfully!")

@app.route('/find_path', methods=['POST'])
def find_path():
    data = request.json
    
    # # Extract coordinates from the request
    # start_lat, start_lng = data['start'][0], data['start'][1]
    # end_lat, end_lng = data['end'][0], data['end'][1]

    # # Finding the nearest edges first then converting them into nodes
    # start_edge = get_nearest_edge(G, start_lat, start_lng)
    # end_edge = get_nearest_edge(G, end_lat, end_lng)
    
    # # 2. Find nearest nodes in the graph
    # start_node = start_edge[0]  # Start node from the nearest edge
    # end_node = end_edge[0]  # End node from the nearest edge

    # t0 = time.time()
    start_coords = (data['start'][0], data['start'][1])
    end_coords = (data['end'][0], data['end'][1])

    # # 1. Find nearest edges
    # start_edge = ox.distance.nearest_edges(G, X=start_coords[1], Y=start_coords[0])
    # end_edge = ox.distance.nearest_edges(G, X=end_coords[1], Y=end_coords[0])
    # print(f"Nearest edges found in: {time.time() - t0:.4f}s")

    # 2. pick the better node from each edge
    # t1 = time.time()
    # start_node = get_closest_node_from_edge(G, start_coords[0], start_coords[1], start_edge)
    # end_node = get_closest_node_from_edge(G, end_coords[0], end_coords[1], end_edge)
    # print(f"Nodes picked in: {time.time() - t1:.4f}s")

    # --- UI SYNC: START BENCHMARK ---
    ui_bench_start = time.time()
    # -------------------------------

    start_node = get_nearest_node(tree, node_ids, start_coords[0], start_coords[1])
    end_node = get_nearest_node(tree, node_ids, end_coords[0], end_coords[1])
    # print(f"Nearest nodes found in: {time.time() - t1:.4f}s")

    # # 3. Custom Dijkstra
    # path_nodes, distance_meters = custom_dijkstra(G, start_node, end_node)

    # 3. A* Pathfinding
    # t2 = time.time()
    path_nodes, distance_meters, nodes_visited = astar_path(G, start_node, end_node)
    # print(f"A* search took: {time.time() - t2:.4f}s")
    
    # --- UI SYNC: END BENCHMARK ---
    execution_time_ms = (time.time() - ui_bench_start) * 1000
    # -----------------------------

    if not path_nodes:
        return jsonify({"error": "No path found"}), 404

    # 4. Calculate Time and convert to kilometers and assume 30 km/h average Delhi traffic speed
    distance_km = distance_meters / 1000
    time_minutes = (distance_km / 45) * 60
        
    # # 4. Convert Node IDs to Lat/Lng 
    # route_coordinates = []
    # for node in path_nodes:
    #     node_data = G.nodes[node]
    #     # x is longitude, y is latitude 
    #     route_coordinates.append([node_data['y'], node_data['x']])

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