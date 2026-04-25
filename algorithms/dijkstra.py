import heapq


def custom_dijkstra(G, start_node, end_node):
    """
    Standard Dijkstra on an OSMnx MultiDiGraph using road length as cost.
    Used for comparison benchmarking against A* in the UI.

    Returns
    -------
    (path, total_distance)
    path           : list of node IDs, or [] if unreachable
    total_distance : total length in metres
    """

    # distances[node] = shortest known distance from start_node
    distances             = {node: float('inf') for node in G.nodes}
    distances[start_node] = 0

    # parents tracks the path for reconstruction
    parents = {node: None for node in G.nodes}

    # Priority queue: (distance, node_id)
    pq = [(0, start_node)]

    while pq:
        current_distance, u = heapq.heappop(pq)

        # Early exit once destination is settled
        if u == end_node:
            break

        # Skip stale entries — a better path to u was already found
        if current_distance > distances[u]:
            continue

        for v, edge_data in G[u].items():
            # G[u][v] is a dict of parallel edges — [0] is the primary edge
            weight   = edge_data[0].get('length', 1)
            distance = current_distance + weight

            if distance < distances[v]:
                distances[v] = distance
                parents[v]   = u
                heapq.heappush(pq, (distance, v))

    # ── PATH RECONSTRUCTION ────────────────────────────────────────────────────
    path = []
    curr = end_node
    while curr is not None:
        path.append(curr)
        curr = parents[curr]
    path.reverse()

    # FIX: "path and" guard — previously crashed with IndexError on empty path
    if path and path[0] == start_node:
        return path, distances[end_node]
    else:
        return [], 0