import heapq
from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):

    r = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(phi1) * cos(phi2) * sin(dlon/2)**2

    return 2 * r * asin(sqrt(a))

def astar_path(graph, start_node, end_node, weight='travel_time'):

    # Pre-cache all coordinates into a simple dict called coords to avoid slow 'graph.nodes[v]' lookups inside the loop
    coords = {node: (data['x'], data['y']) for node, data in graph.nodes(data=True)}

    max_speed_mps = 22.22

    distances = {node: float('inf') for node in graph.nodes}
    distances[start_node] = 0
    parents = {node: None for node in graph.nodes}

    # Get goal coordinates for the heuristic
    goal_lat, goal_lon = coords[end_node]

    # Priority queue
    # [(priority, distance, node_id)]
    pq = [(0, 0, start_node)]

    nodes_visited = 0

    while pq:
        priority, current_cost, u = heapq.heappop(pq)

        nodes_visited += 1
        
        if u==end_node:
            break

        if current_cost > distances[u]:
            continue

        # Relax edges
        for v, edge_data in graph[u].items():
            edge_weight = min(e.get(weight, 1) for e in edge_data.values())
            new_cost = current_cost + edge_weight

            if new_cost < distances[v]:
                distances[v] = new_cost
                parents[v] = u

                # Haversine heuristic
                v_lon, v_lat = coords[v]
                h_dist = haversine(v_lon, v_lat,
                              goal_lon, goal_lat)

                h = h_dist/max_speed_mps if weight == 'travel_time' else h_dist
                heapq.heappush(pq, (new_cost + h, new_cost, v))


    # Reconstruct path
    path = []
    curr = end_node
    while curr is not None:
        path.append(curr)
        curr = parents[curr]

    path = path[::-1]

    if path and path[0] == start_node:
        return path, distances[end_node], nodes_visited
    else:
        return [], 0, nodes_visited 
