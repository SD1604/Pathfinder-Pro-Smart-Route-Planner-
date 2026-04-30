import heapq
from math import radians, cos, sin, asin, sqrt


def haversine(lon1, lat1, lon2, lat2):
    """Same haversine as before — unchanged."""
    r = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a    = sin(dlat / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def bidir_astar_path(graph, start_node, end_node, weight='travel_time'):
    """
    Bidirectional A* on an OSMnx MultiDiGraph.

    Runs two simultaneous A* searches:
      - Forward  search: expands from start_node toward end_node
      - Backward search: expands from end_node toward start_node
                         using the REVERSE graph (flipped edges)

    Stops when the two frontiers meet and we've confirmed the
    best-known meeting path can't be improved further.

    Returns
    -------
    (path, total_cost, nodes_visited)
    Same contract as astar_path — drop-in replacement.
    """

    # ── SETUP ─────────────────────────────────────────────────────────────────

    # Pre-cache coordinates exactly like vanilla A*
    coords = {node: (data['x'], data['y'])
              for node, data in graph.nodes(data=True)}

    max_speed_mps = 22.22  # admissible heuristic cap — same as before

    start_lon, start_lat = coords[start_node]
    goal_lon,  goal_lat  = coords[end_node]

    # The backward search needs to traverse edges in reverse.
    # OSMnx provides graph.reverse() for this — it flips all directed edges
    # so the backward search can "walk backwards" toward start.
    rev_graph = graph.reverse(copy=False)  # copy=False = no memory overhead

    # ── FORWARD STATE ─────────────────────────────────────────────────────────

    f_dist           = {n: float('inf') for n in graph.nodes}
    f_dist[start_node] = 0
    f_par            = {n: None for n in graph.nodes}

    # (f_score, g_score, node)
    f_pq = [(0, 0, start_node)]

    # Which nodes the forward search has SETTLED (popped and fully processed)
    # Key insight: a node is "settled" only when it's been popped — not just
    # pushed. Being pushed means "we found A path", settled means "we found
    # THE BEST path to this node".
    f_settled = set()

    # ── BACKWARD STATE ────────────────────────────────────────────────────────

    b_dist           = {n: float('inf') for n in graph.nodes}
    b_dist[end_node] = 0
    b_par            = {n: None for n in graph.nodes}

    b_pq = [(0, 0, end_node)]
    b_settled = set()

    # ── TERMINATION TRACKING ──────────────────────────────────────────────────

    # best_cost: the shortest complete path we've found SO FAR
    # (path that has been touched by both searches)
    # We don't stop the moment frontiers touch — we keep going until
    # we can PROVE no shorter path exists.
    best_cost   = float('inf')
    meeting_node = None
    nodes_visited = 0

    # ── MAIN LOOP ─────────────────────────────────────────────────────────────

    while f_pq or b_pq:

        # ── BIDIRECTIONAL TERMINATION CONDITION ───────────────────────────────
        # We can stop when the top of BOTH priority queues combined
        # can't beat best_cost.
        #
        # Why? Because A* processes nodes in non-decreasing f-score order.
        # If min(f_fwd) + min(f_bwd) >= best_cost, any future path through
        # unsettled nodes will cost at least best_cost — so we're done.
        #
        # This is the key correctness guarantee of bidirectional A*.
        f_min = f_pq[0][0] if f_pq else float('inf')
        b_min = b_pq[0][0] if b_pq else float('inf')
        if f_min + b_min >= best_cost:
            break

        # ── FORWARD STEP ──────────────────────────────────────────────────────
        if f_pq:
            _, g_u, u = heapq.heappop(f_pq)
            nodes_visited += 1

            # Stale entry — we already settled u with a lower cost
            if u in f_settled:
                continue
            if g_u > f_dist[u]:
                continue

            f_settled.add(u)

            for v, edge_data in graph[u].items():
                edge_w  = min(e.get(weight, 1) for e in edge_data.values())
                new_g   = g_u + edge_w

                if new_g < f_dist[v]:
                    f_dist[v] = new_g
                    f_par[v]  = u

                    v_lon, v_lat = coords[v]
                    h_dist = haversine(v_lon, v_lat, goal_lon, goal_lat)
                    h      = h_dist / max_speed_mps if weight == 'travel_time' else h_dist

                    heapq.heappush(f_pq, (new_g + h, new_g, v))

                # ── MEETING POINT CHECK ───────────────────────────────────────
                # If the backward search has already settled v, we have a
                # complete candidate path: start → ... → u → v → ... → goal
                # Its total cost is f_dist[u] + edge_w + b_dist[v]
                if v in b_settled:
                    candidate = f_dist[u] + edge_w + b_dist[v]
                    if candidate < best_cost:
                        best_cost    = candidate
                        meeting_node = v

        # ── BACKWARD STEP ─────────────────────────────────────────────────────
        if b_pq:
            _, g_u, u = heapq.heappop(b_pq)
            nodes_visited += 1

            if u in b_settled:
                continue
            if g_u > b_dist[u]:
                continue

            b_settled.add(u)

            # Walk the REVERSED graph — same logic, goal and start swapped
            for v, edge_data in rev_graph[u].items():
                edge_w  = min(e.get(weight, 1) for e in edge_data.values())
                new_g   = g_u + edge_w

                if new_g < b_dist[v]:
                    b_dist[v] = new_g
                    b_par[v]  = u  # in backward search, parent means "next node toward goal"

                    v_lon, v_lat = coords[v]
                    h_dist = haversine(v_lon, v_lat, start_lat, start_lon)
                    h      = h_dist / max_speed_mps if weight == 'travel_time' else h_dist

                    heapq.heappush(b_pq, (new_g + h, new_g, v))

                if v in f_settled:
                    candidate = b_dist[u] + edge_w + f_dist[v]
                    if candidate < best_cost:
                        best_cost    = candidate
                        meeting_node = v

    # ── PATH RECONSTRUCTION ───────────────────────────────────────────────────

    if meeting_node is None or best_cost == float('inf'):
        return [], 0, nodes_visited

    # Forward half: walk f_par from meeting_node back to start, then reverse
    forward_path = []
    curr = meeting_node
    while curr is not None:
        forward_path.append(curr)
        curr = f_par[curr]
    forward_path.reverse()   # now: start → ... → meeting_node

    # Backward half: walk b_par from meeting_node forward to goal
    # b_par[v] = u means "u was expanded when we reached v in backward search"
    # which means in the real graph, the edge goes v → u (forward direction: u → v? no)
    # Actually b_par[v] = the node we came FROM in the backward search,
    # which means in the original graph: that node comes AFTER v on the path to goal.
    backward_path = []
    curr = b_par[meeting_node]  # skip meeting_node itself (already in forward_path)
    while curr is not None:
        backward_path.append(curr)
        curr = b_par[curr]
    # backward_path is already in order: meeting_node+1 → ... → goal

    path = forward_path + backward_path

    if path[0] == start_node and path[-1] == end_node:
        return path, best_cost, nodes_visited
    else:
        return [], 0, nodes_visited