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
