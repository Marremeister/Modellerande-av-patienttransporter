import random

class Graph:
    def __init__(self, directed=False):
        """Initialize a graph with optional directed edges and coordinate tracking."""
        self.adjacency_list = {}
        self.coordinates = {}  # NEW: Store coordinates for each node
        self.directed = directed

    def add_node(self, node, x=None, y=None):
        """Adds a node to the graph with optional coordinates."""
        if node not in self.adjacency_list:
            self.adjacency_list[node] = {}
            self.coordinates[node] = (x, y) if x is not None and y is not None else (0, 0)

    def set_node_coordinates(self, node, x, y):
        """Sets fixed coordinates for a node."""
        if node in self.adjacency_list:
            self.coordinates[node] = (x, y)

    def get_node_coordinates(self, node):
        """Returns the coordinates of a node."""
        return self.coordinates.get(node, (0, 0))

    def add_edge(self, node1, node2, weight=1):
        """Adds an edge between two nodes, with an optional weight."""
        if node1 not in self.adjacency_list:
            self.add_node(node1)
        if node2 not in self.adjacency_list:
            self.add_node(node2)

        self.adjacency_list[node1][node2] = weight
        if not self.directed:
            self.adjacency_list[node2][node1] = weight

    def get_hospital_graph(self):
        """Returns graph data including nodes, edges, and positions with slight randomness."""
        return {
            "nodes": [{"id": node,
                       "x": self.coordinates[node][0] + random.uniform(-10, 10),  # 🔹 Add slight randomness
                       "y": self.coordinates[node][1] + random.uniform(-10, 10)}  # 🔹 Add slight randomness
                      for node in self.adjacency_list.keys()],
            "edges": [{"source": n1, "target": n2, "distance": self.adjacency_list[n1][n2]}
                      for n1 in self.adjacency_list for n2 in self.adjacency_list[n1]]
        }

    def get_edge_weight(self, node1, node2):
        """Returnerar vikten mellan två noder om kanten existerar, annars None."""
        return self.adjacency_list.get(node1, {}).get(node2, None)

    def get_nodes(self):
        """Returns a list of all nodes in the graph."""
        return list(self.adjacency_list.keys())
