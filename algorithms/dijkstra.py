import heapq

def custom_dijkstra(G, start_node, end_node):
    # 1. Initialize data structures
    # distances: {node_id: distance_value}
    distances = {node: float('inf') for node in G.nodes}
    distances[start_node] = 0
    
    # parents: {child_node: parent_node} for backtracking the path
    parents = {node: None for node in G.nodes}
    
    # priority_queue: [(distance, node_id)]
    pq = [(0, start_node)]
    
    while pq:
        current_distance, u = heapq.heappop(pq)
        
        # If we reached the destination, we can stop early (Optimization)
        if u == end_node:
            break
            
        # Standard Dijkstra check: ignore if we found a better path already
        if current_distance > distances[u]:
            continue
            
        # 2. Relax edges
        # G[u].items() gives us all neighbors 'v' and edge data
        for v, edge_data in G[u].items():
            # We use [0] because OSMnx graphs can have multiple edges between nodes
            weight = edge_data[0].get('length', 1) 
            
            distance = current_distance + weight
            
            if distance < distances[v]:
                distances[v] = distance
                parents[v] = u
                heapq.heappush(pq, (distance, v))
                
    # 3. Path Reconstruction
    path = []
    curr = end_node
    while curr is not None:
        path.append(curr)
        curr = parents[curr]
    
    # Reverse the path to get it from Start -> End
    path = path[::-1]
    
    if path and path[0] == start_node:
        total_distance = distances[end_node]
        return path, total_distance
    else:
        return [], 0
    
    print("Dijkstra Engine logic loaded.")