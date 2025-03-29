# Model/data_processor/graph_builder.py
"""
Class for building a hospital graph based on transport data analysis.
"""
import logging
import random
from Model.graph_model import Graph
from Model.model_pathfinder import Pathfinder


class HospitalGraphBuilder:
    """
    Builds a hospital graph from analyzed transport data, using an incremental
    approach to create realistic connections.
    """

    def __init__(self, analyzer, time_factor=1.0):
        """
        Initialize the HospitalGraphBuilder.

        Args:
            analyzer: TransportDataAnalyzer instance with processed data
            time_factor: Factor to scale all times by (e.g., 0.1 for faster simulation)
        """
        self.analyzer = analyzer
        self.time_factor = time_factor
        self.graph = Graph(directed=False)
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a logger for the HospitalGraphBuilder."""
        logger = logging.getLogger("HospitalGraphBuilder")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def build_graph(self, path_threshold=1.25):
        """
        Build the hospital graph incrementally, adding nodes and edges
        based on the transport data.

        Args:
            path_threshold: Threshold for adding direct edges (if existing path is
                           path_threshold times longer than expected, add direct edge)

        Returns:
            Graph: The constructed hospital graph
        """
        self.logger.info("Building hospital graph...")

        # Add all departments as nodes
        departments = self.analyzer.get_all_departments()
        for dept in departments:
            self.graph.add_node(dept)

        self.logger.info(f"Added {len(departments)} nodes to the graph")

        # Get median transport times between departments
        median_times = self.analyzer.get_median_transport_times()

        # Create a sorted list of department pairs by transport time
        sorted_pairs = sorted(median_times.items(), key=lambda x: x[1])

        # Create a temporary Hospital for the pathfinder
        temp_hospital = type('TempHospital', (), {'get_graph': lambda: self.graph})()
        pathfinder = Pathfinder(temp_hospital)

        # Track connections that we've already examined
        examined_connections = set()
        added_edges = 0
        skipped_edges = 0

        # Iterate through pairs from shortest to longest time
        for (origin, dest), median_time in sorted_pairs:
            # Skip self-connections
            if origin == dest:
                continue

            # Skip if we've already examined this connection
            if (origin, dest) in examined_connections or (dest, origin) in examined_connections:
                continue

            examined_connections.add((origin, dest))

            # Scale the time by the factor
            scaled_time = median_time * self.time_factor

            try:
                # Check if there's already a path
                path, distance = pathfinder.dijkstra(origin, dest)

                # If no path exists, add direct edge
                if not path or len(path) < 2:
                    self.graph.add_edge(origin, dest, scaled_time)
                    added_edges += 1
                    self.logger.debug(f"Added edge {origin} -> {dest} (time: {scaled_time:.1f}s) - No existing path")
                    continue

                # If path is significantly longer than expected, add direct edge
                if distance > scaled_time * path_threshold:
                    self.graph.add_edge(origin, dest, scaled_time)
                    added_edges += 1
                    self.logger.debug(f"Added edge {origin} -> {dest} (time: {scaled_time:.1f}s) - "
                                      f"Existing path too long ({distance:.1f}s vs {scaled_time:.1f}s)")
                else:
                    # Existing path is good enough
                    skipped_edges += 1
                    self.logger.debug(f"Skipped edge {origin} -> {dest} - "
                                      f"Existing path is sufficient ({distance:.1f}s vs {scaled_time:.1f}s)")

            except Exception as e:
                # If there's an error in pathfinding, add direct edge to be safe
                self.logger.warning(f"Error in pathfinding from {origin} to {dest}: {str(e)}")
                self.graph.add_edge(origin, dest, scaled_time)
                added_edges += 1

        self.logger.info(f"Graph building complete. Added {added_edges} edges, skipped {skipped_edges} edges.")
        return self.graph

    def add_edges_from_expert_input(self, edge_list):
        """
        Add or update edges based on expert input.

        Args:
            edge_list: List of tuples (origin, dest, time) to add/update

        Returns:
            int: Number of edges added/updated
        """
        added = 0
        for origin, dest, time in edge_list:
            if origin in self.graph.adjacency_list and dest in self.graph.adjacency_list:
                self.graph.add_edge(origin, dest, time * self.time_factor)
                added += 1
            else:
                self.logger.warning(f"Cannot add edge {origin} -> {dest}: Node(s) do not exist in graph")

        self.logger.info(f"Added/updated {added} edges from expert input")
        return added

    def validate_graph_connectivity(self):
        """
        Ensure the graph is fully connected by adding edges if necessary.

        Returns:
            bool: True if the graph was already connected, False if edges were added
        """
        self.logger.info("Validating graph connectivity...")

        # Get all nodes
        nodes = list(self.graph.adjacency_list.keys())
        if not nodes:
            self.logger.warning("No nodes in graph. Nothing to validate.")
            return True

        # Create a set of connected nodes, starting with the first node
        connected = {nodes[0]}
        frontier = [nodes[0]]

        # Breadth-first search to find all connected nodes
        while frontier:
            current = frontier.pop(0)
            neighbors = self.graph.adjacency_list[current].keys()

            for neighbor in neighbors:
                if neighbor not in connected:
                    connected.add(neighbor)
                    frontier.append(neighbor)

        # Check for disconnected nodes
        disconnected = set(nodes) - connected
        if not disconnected:
            self.logger.info("Graph is fully connected.")
            return True

        # Add edges to connect disconnected nodes
        self.logger.warning(f"Found {len(disconnected)} disconnected nodes. Adding connections...")

        for node in disconnected:
            # Find the closest connected node (by name similarity as a heuristic)
            connected_node = min(connected, key=lambda x: _name_similarity(node, x))

            # Add an edge with a reasonable weight
            average_weight = self._get_average_edge_weight()
            self.graph.add_edge(node, connected_node, average_weight)

            # Add to connected set
            connected.add(node)

        self.logger.info("Graph connectivity ensured.")
        return False

    def _get_average_edge_weight(self):
        """Calculate the average edge weight in the graph."""
        total = 0
        count = 0

        for source in self.graph.adjacency_list:
            for target, weight in self.graph.adjacency_list[source].items():
                total += weight
                count += 1

        return total / max(1, count)  # Avoid division by zero


def _name_similarity(str1, str2):
    """Simple string similarity metric based on common substrings."""
    max_len = max(len(str1), len(str2))
    if max_len == 0:
        return 0

    # Count common characters
    common = sum(1 for c1, c2 in zip(str1, str2) if c1 == c2)
    return common / max_len