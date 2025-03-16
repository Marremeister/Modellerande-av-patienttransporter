import networkx as nx
import matplotlib.pyplot as plt


class HospitalView:
    @staticmethod
    def display_graph(graph):
        """Displays the hospital graph using NetworkX and Matplotlib."""
        G = nx.Graph()

        for node in graph.adjacency_list:
            G.add_node(node)

        for node, edges in graph.adjacency_list.items():
            for neighbor, weight in edges.items():
                G.add_edge(node, neighbor, weight=weight)

        pos = nx.spring_layout(G)
        labels = nx.get_edge_attributes(G, 'weight')
        nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=2000, edge_color='gray')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)
        plt.show()
