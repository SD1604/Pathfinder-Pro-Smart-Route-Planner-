from flask import Flask, request, jsonify
from flask_cors import CORS
import osmnx as ox
from algorithms.dijkstra import custom_dijkstra
from graph.graph_loader import initialize_graph
from utils.geo_utils import get_nearest_node, get_nearest_edge, get_closest_node_from_edge

app = Flask(__name__)
CORS(app)  # This allows our HTML file to talk to this Python server

# 1. Load the graph once when the server starts
print("Loading map data... please wait.")
G = initialize_graph()
print("Map loaded successfully!")

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

    start_coords = (data['start'][0], data['start'][1])
    end_coords = (data['end'][0], data['end'][1])

    # 1. Find nearest edges (returns tuples like (u, v, key))
    start_edge = ox.distance.nearest_edges(G, X=start_coords[1], Y=start_coords[0])
    end_edge = ox.distance.nearest_edges(G, X=end_coords[1], Y=end_coords[0])

    # 2. Use the helper to pick the better node from each edge
    start_node = get_closest_node_from_edge(G, start_coords[0], start_coords[1], start_edge)
    end_node = get_closest_node_from_edge(G, end_coords[0], end_coords[1], end_edge)

    # 3. Run Custom Dijkstra (now returns distance too)
    path_nodes, distance_meters = custom_dijkstra(G, start_node, end_node)
    
    if not path_nodes:
        return jsonify({"error": "No path found"}), 404

    # 4. Calculate Time (Time = Distance / Speed)
    # Convert meters to km, and assume 30 km/h average Delhi traffic speed
    distance_km = distance_meters / 1000
    time_minutes = (distance_km / 45) * 60
        
    # 4. Convert Node IDs to Lat/Lng pairs for the frontend
    route_coordinates = []
    for node in path_nodes:
        node_data = G.nodes[node]
        # x is longitude, y is latitude in OSMnx
        route_coordinates.append([node_data['y'], node_data['x']])
        
    return jsonify({
        "path": route_coordinates,
        "distance": round(distance_km, 2),
        "time": round(time_minutes, 1)
    })

if __name__ == '__main__':
    app.run(port=5000, debug=True)