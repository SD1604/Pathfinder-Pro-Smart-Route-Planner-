import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import osmnx as ox
from algorithms.dijkstra import custom_dijkstra
from algorithms.astar_path import astar_path
from scipy.spatial import KDTree
import pandas as pd
from graph.graph_loader import initialize_graph
from utils.geo_utils import get_nearest_node, build_spatial_index

# ── APP SETUP ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'pathfinder-pro-secret'
CORS(app, resources={r"/*": {"origins": "*"}})

# Why SocketIO? — Foundation for pushing live waterlogging/market alerts
# to the browser later without the user needing to refresh.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# ── GRAPH LOADING ──────────────────────────────────────────────────────────────
print("Loading map data... please wait.")
G = initialize_graph()

print("Imputing Road Speeds and Travel Times...")
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)

tree, node_ids = build_spatial_index(G)

# Pre-cache node coordinates — avoids slow graph.nodes[v] lookups per request
node_coords = {node: [data['y'], data['x']] for node, data in G.nodes(data=True)}
print("Map and Cache loaded successfully!")


# ── ROUTE CACHE ────────────────────────────────────────────────────────────────
# Why cache? — AIIMS → Connaught Place is queried hundreds of times a day.
# Computing A* every single time wastes CPU. Cache stores the result for 5 min.
# Key: (start_node, end_node, mode)  Value: {result_dict, expires_at}
_route_cache = {}
_cache_lock  = threading.Lock()
CACHE_TTL_SECONDS = 300  # 5 minutes


def cache_get(key):
    with _cache_lock:
        entry = _route_cache.get(key)
        if entry and datetime.utcnow() < entry['expires_at']:
            return entry['data']
        if entry:
            del _route_cache[key]  # expired — remove it
        return None


def cache_set(key, data):
    with _cache_lock:
        _route_cache[key] = {
            'data':       data,
            'expires_at': datetime.utcnow() + timedelta(seconds=CACHE_TTL_SECONDS)
        }


# ── TRANSPORT MODE CONFIGURATION ───────────────────────────────────────────────
# Why modes? — A cyclist can't use the expressway; a walker ignores road speeds.
# Each mode gets its own speed cap and the weight used for edge cost.
MODE_CONFIG = {
    'drive': {
        'weight':    'travel_time',   # OSMnx travel_time uses real speed limits
        'speed_cap': 80,              # km/h — cap for Delhi urban driving
        'label':     'Driving'
    },
    'walk': {
        'weight':    'length',        # walking = shortest distance, not fastest time
        'speed_cap': 5,               # km/h
        'label':     'Walking'
    },
    'cycle': {
        'weight':    'length',        # cycling also optimises distance
        'speed_cap': 20,              # km/h
        'label':     'Cycling'
    }
}


# ── ROAD NAME EXTRACTION ───────────────────────────────────────────────────────
# Why extract names? — The frontend needs "Ring Road → NH48 → Mathura Road"
# to build the turn-by-turn directions panel.
def extract_road_names(G, path_nodes):
    """
    Walk the path node-by-node, extract the road name from each OSM edge.
    Returns a list of instruction dicts:
      [{ "road": "Outer Ring Road", "from_node": 123, "to_node": 456 }, ...]
    Consecutive segments on the same road are merged into one instruction.
    """
    if len(path_nodes) < 2:
        return []

    instructions = []
    current_road = None
    segment_start = path_nodes[0]

    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        edge_data = G.get_edge_data(u, v)
        if edge_data is None:
            road_name = "Unknown Road"
        else:
            # OSMnx stores edge data under key 0 for the first (often only) edge
            attrs = edge_data.get(0, {})
            raw   = attrs.get('name', None)

            if isinstance(raw, list):
                road_name = raw[0]          # some OSM edges have multiple names
            elif isinstance(raw, str):
                road_name = raw
            else:
                road_name = attrs.get('ref', 'Unnamed Road')  # use road ref if no name

        # Only emit a new instruction when the road name changes
        if road_name != current_road:
            if current_road is not None:
                instructions.append({
                    "road":       current_road,
                    "from_node":  segment_start,
                    "to_node":    u
                })
            current_road  = road_name
            segment_start = u

    # Append the final segment
    if current_road is not None:
        instructions.append({
            "road":      current_road,
            "from_node": segment_start,
            "to_node":   path_nodes[-1]
        })

    return instructions


def build_directions(instructions, path_nodes, G):
    """
    Convert raw road-name instructions into human-readable turn directions.
    e.g. "Head along Outer Ring Road", "Turn onto NH48"
    """
    if not instructions:
        return []

    directions = []
    for i, step in enumerate(instructions):
        if i == 0:
            verb = "Head along"
        else:
            verb = "Turn onto"

        directions.append({
            "step":        i + 1,
            "instruction": f"{verb} {step['road']}"
        })

    directions.append({
        "step":        len(directions) + 1,
        "instruction": "Arrive at your destination"
    })

    return directions


# ── MAIN ROUTE ENDPOINT ────────────────────────────────────────────────────────
@app.route('/find_path', methods=['POST'])
def find_path():
    data = request.json

    # Basic input validation — prevents crashes from malformed requests
    if not data or 'start' not in data or 'end' not in data:
        return jsonify({"error": "Missing start or end coordinates"}), 400

    start_coords = (data['start'][0], data['start'][1])
    end_coords   = (data['end'][0],   data['end'][1])
    mode         = data.get('mode', 'drive')  # default to driving

    if mode not in MODE_CONFIG:
        return jsonify({"error": f"Invalid mode '{mode}'. Use: drive, walk, cycle"}), 400

    cfg    = MODE_CONFIG[mode]
    weight = cfg['weight']

    # ── NEAREST NODE LOOKUP ──────────────────────────────────────────────────
    start_node = get_nearest_node(tree, node_ids, start_coords[0], start_coords[1])
    end_node   = get_nearest_node(tree, node_ids, end_coords[0],   end_coords[1])

    # ── CACHE CHECK ─────────────────────────────────────────────────────────
    # Why check cache before A*? — Saves 100–500ms on repeated popular routes.
    cache_key    = (start_node, end_node, mode)
    cached_result = cache_get(cache_key)
    if cached_result:
        cached_result['cache_hit'] = True
        return jsonify(cached_result)

    # ── A* PATHFINDING ───────────────────────────────────────────────────────
    ui_bench_start = time.time()

    try:
        path_nodes, total_cost, nodes_visited = astar_path(
            G, start_node, end_node, weight=weight
        )
    except Exception as e:
        print(f"A* error: {e}")
        return jsonify({"error": "Pathfinding failed internally"}), 500

    execution_time_ms = (time.time() - ui_bench_start) * 1000

    if not path_nodes:
        return jsonify({"error": "No path found between these points"}), 404

    # ── DISTANCE & TIME CALCULATION ──────────────────────────────────────────
    distance_meters = sum(
        G.get_edge_data(u, v)[0].get('length', 0)
        for u, v in zip(path_nodes[:-1], path_nodes[1:])
    )
    distance_km = distance_meters / 1000

    # For drive: total_cost is travel_time (seconds) from A* weight
    # For walk/cycle: total_cost is length (metres) — convert to time using speed
    if weight == 'travel_time':
        time_minutes = total_cost / 60
    else:
        speed_mps    = (cfg['speed_cap'] * 1000) / 3600
        time_minutes = (distance_meters / speed_mps) / 60

    # ── ROAD NAMES & DIRECTIONS ──────────────────────────────────────────────
    # Why return road names from backend? — The graph is on the server.
    # The frontend has no access to OSM edge attributes.
    road_instructions = extract_road_names(G, path_nodes)
    directions        = build_directions(road_instructions, path_nodes, G)

    # ── COORDINATES ──────────────────────────────────────────────────────────
    route_coordinates = [node_coords[node] for node in path_nodes]

    # ── BUILD RESPONSE ───────────────────────────────────────────────────────
    result = {
        "path":           route_coordinates,
        "distance":       round(distance_km, 2),
        "time":           round(time_minutes, 1),
        "execution_time": round(execution_time_ms, 2),
        "nodes_visited":  nodes_visited,
        "mode":           mode,
        "mode_label":     cfg['label'],
        "directions":     directions,
        "cache_hit":      False
    }

    # Store in cache for next identical request
    cache_set(cache_key, result)

    return jsonify(result)


# ── WEBSOCKET EVENTS ───────────────────────────────────────────────────────────
# Why WebSocket? — When we add waterlogging data, the server needs to PUSH
# updated road conditions to the browser without the user refreshing.
# This lays the foundation for that. Right now it just echoes a connect event.

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to Pathfinder Pro live updates'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on('subscribe_conditions')
def handle_subscribe(data):
    """
    Future use: client sends their current bounding box,
    server will push road condition updates for that area.
    """
    emit('conditions_ack', {
        'message': 'Subscribed to live conditions (waterlogging/markets coming soon)'
    })


# ── UTILITY ENDPOINTS ──────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    """Simple health check — useful for deployment monitoring."""
    return jsonify({
        "status":      "ok",
        "nodes":       len(G.nodes),
        "edges":       len(G.edges),
        "cache_size":  len(_route_cache)
    })


@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Manual cache clear endpoint — useful during development."""
    with _cache_lock:
        _route_cache.clear()
    return jsonify({"message": "Cache cleared"})


# ── ENTRY POINT ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # Use socketio.run instead of app.run — required for WebSocket support
    socketio.run(app, host="0.0.0.0", port=port, debug=False)