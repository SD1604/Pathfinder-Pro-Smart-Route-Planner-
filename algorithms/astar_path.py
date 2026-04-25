import heapq
from math import radians, cos, sin, asin, sqrt


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate straight-line distance (metres) between two lat/lon points.
    Used as the A* heuristic — gives a lower-bound estimate of remaining cost.
    """
    r = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a    = sin(dlat / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def astar_path(graph, start_node, end_node, weight='travel_time'):
    """
    A* shortest path on an OSMnx MultiDiGraph.

    Parameters
    ----------
    graph      : OSMnx graph (loaded from GraphML)
    start_node : integer OSM node ID
    end_node   : integer OSM node ID
    weight     : edge attribute to use as cost — 'travel_time' for drive,
                 'length' for walk/cycle

    Returns
    -------
    (path, total_cost, nodes_visited)
    path         : list of node IDs from start to end, or [] if unreachable
    total_cost   : accumulated cost along the path (seconds or metres)
    nodes_visited: how many nodes were popped from the priority queue
    """

    # Pre-cache all coordinates once — avoids slow graph.nodes[v] dict lookups
    # inside the hot loop which runs hundreds of thousands of times per query.
    # coords[node] = (longitude, latitude)  — OSMnx stores x=lon, y=lat
    coords = {node: (data['x'], data['y']) for node, data in graph.nodes(data=True)}

    # Max speed used to compute the heuristic for travel_time weight.
    # 22.22 m/s = 80 km/h — the fastest plausible speed on Delhi roads.
    # This keeps the heuristic admissible (never overestimates real cost).
    max_speed_mps = 22.22

    # distances[node] = best known cost to reach that node from start
    distances              = {node: float('inf') for node in graph.nodes}
    distances[start_node]  = 0

    # parents[node] = which node we came from — used for path reconstruction
    parents               = {node: None for node in graph.nodes}

    # FIX: coords stores (x=lon, y=lat) — unpack correctly
    # Previously: goal_lat, goal_lon = coords[end_node]  ← WRONG order
    goal_lon, goal_lat = coords[end_node]

    # Priority queue entries: (f_score, g_score, node_id)
    # f = g + h  where g = real cost so far, h = heuristic estimate to goal
    pq            = [(0, 0, start_node)]
    nodes_visited = 0

    while pq:
        priority, current_cost, u = heapq.heappop(pq)
        nodes_visited += 1

        # Early exit — we've reached the destination
        if u == end_node:
            break

        # Stale entry check — we already found a better path to u, skip this one.
        # FIX: removed the old "or current_cost > 500000" magic number which
        # silently broke routes longer than ~8 hours of travel time.
        if current_cost > distances[u]:
            continue

        # Relax each outgoing edge from u
        for v, edge_data in graph[u].items():
            # OSMnx MultiDiGraph can have parallel edges between the same pair.
            # We take the minimum cost edge — the fastest/shortest option.
            edge_weight = min(e.get(weight, 1) for e in edge_data.values())
            new_cost    = current_cost + edge_weight

            if new_cost < distances[v]:
                distances[v] = new_cost
                parents[v]   = u

                # Heuristic: straight-line distance ÷ max speed = min possible time
                v_lon, v_lat = coords[v]
                h_dist = haversine(v_lon, v_lat, goal_lon, goal_lat)
                h      = h_dist / max_speed_mps if weight == 'travel_time' else h_dist

                heapq.heappush(pq, (new_cost + h, new_cost, v))

    # ── PATH RECONSTRUCTION ────────────────────────────────────────────────────
    # Walk backwards through the parents dict from end → start, then reverse.
    path = []
    curr = end_node
    while curr is not None:
        path.append(curr)
        curr = parents[curr]
    path.reverse()

    # FIX: "path and" guard — prevents IndexError if path is empty (no route found)
    if path and path[0] == start_node:
        return path, distances[end_node], nodes_visited
    else:
        return [], 0, nodes_visited