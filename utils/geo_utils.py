import osmnx as ox
from scipy.spatial import KDTree
import pandas as pd

def build_spatial_index(graph):
    nodes_data = pd.DataFrame.from_dict(dict(graph.nodes(data=True)), orient='index')
    coords = nodes_data[['y','x']].values
    node_ids = nodes_data.index.values

    tree = KDTree(coords)
    return tree, node_ids

def get_nearest_node(tree, node_ids, lat, lon):

    _, index = tree.query([lat, lon])
    return node_ids[index]



# def get_nearest_edge(graph, lat, lon):

#     nearest_edge = ox.nearest_edges(graph, X=lon, Y=lat)
#     return nearest_edge

# def get_closest_node_from_edge(G, click_lat, click_lng, edge_tuple):
#     u, v, key = edge_tuple
    
#     # Get coordinates for both nodes
#     node_u = G.nodes[u]
#     node_v = G.nodes[v]
    
#     # Calculate simple squared distance
#     dist_u = (node_u['y'] - click_lat)**2 + (node_u['x'] - click_lng)**2
#     dist_v = (node_v['y'] - click_lat)**2 + (node_v['x'] - click_lng)**2
    
#     # ID of the closer node
#     return u if dist_u < dist_v else v
