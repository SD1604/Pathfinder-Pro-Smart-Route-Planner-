import osmnx as ox

def get_nearest_node(graph, lat, lon):

    nearest_node_id = ox.nearest_nodes(graph, X=lon, Y=lat)
    return nearest_node_id

def get_nearest_edge(graph, lat, lon):

    nearest_edge = ox.nearest_edges(graph, X=lon, Y=lat)
    return nearest_edge

def get_closest_node_from_edge(G, click_lat, click_lng, edge_tuple):
    u, v, key = edge_tuple
    
    # Get coordinates for both nodes
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    # Calculate simple squared distance
    dist_u = (node_u['y'] - click_lat)**2 + (node_u['x'] - click_lng)**2
    dist_v = (node_v['y'] - click_lat)**2 + (node_v['x'] - click_lng)**2
    
    # ID of the closer node
    return u if dist_u < dist_v else v
