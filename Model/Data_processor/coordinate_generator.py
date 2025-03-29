# Model/data_processor/coordinate_generator.py
"""
Class for generating coordinates for hospital departments based on transport times.
Uses a force-directed layout algorithm to position nodes.
"""
import numpy as np
import logging
import random
from scipy.spatial.distance import pdist, squareform


class CoordinateGenerator:
    """
    Generates 2D coordinates for hospital departments based on their transport times.
    Uses a force-directed layout algorithm to position nodes in a way that approximates
    the relative distances between them.
    """

    def __init__(self, graph, canvas_width=800, canvas_height=600):
        """
        Initialize the CoordinateGenerator.

        Args:
            graph: Graph instance with nodes and edges
            canvas_width: Width of the visualization canvas
            canvas_height: Height of the visualization canvas
        """
        self.graph = graph
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a logger for the CoordinateGenerator."""
        logger = logging.getLogger("CoordinateGenerator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def generate_coordinates(self, iterations=1000, temperature=0.1, cooling_factor=0.98):
        """
        Generate coordinates for all nodes using force-directed placement.
        This algorithm positions nodes so that connected nodes are closer together,
        with edge weights influencing the ideal distance.

        Args:
            iterations: Number of iterations to run the force-directed algorithm
            temperature: Initial "temperature" controlling how much nodes can move
            cooling_factor: Factor to reduce temperature each iteration

        Returns:
            bool: True if coordinates were generated successfully
        """
        self.logger.info("Generating coordinates using force-directed placement...")

        # Get all nodes
        nodes = list(self.graph.adjacency_list.keys())
        if not nodes:
            self.logger.error("No nodes in graph. Cannot generate coordinates.")
            return False

        n_nodes = len(nodes)

        # Create a node_index mapping for easier reference
        node_index = {node: i for i, node in enumerate(nodes)}

        # Initialize random positions
        positions = np.random.rand(n_nodes, 2)  # Random 2D coordinates
        positions[:, 0] *= self.canvas_width * 0.8  # Scale to canvas
        positions[:, 1] *= self.canvas_height * 0.8

        # Center the positions
        positions[:, 0] += self.canvas_width * 0.1
        positions[:, 1] += self.canvas_height * 0.1

        # Create distance matrix based on edge weights
        ideal_distances = np.zeros((n_nodes, n_nodes))

        # Set ideal distances based on edge weights
        # (we use sqrt of time to make the layout more compact)
        for i, node_i in enumerate(nodes):
            for j, node_j in enumerate(nodes):
                if i == j:
                    continue

                # Try to get edge weight in both directions
                weight_ij = self.graph.get_edge_weight(node_i, node_j)
                weight_ji = self.graph.get_edge_weight(node_j, node_i)

                if weight_ij is not None:
                    # sqrt of time to make layout more compact
                    ideal_distances[i, j] = np.sqrt(weight_ij) * 5
                elif weight_ji is not None:
                    ideal_distances[i, j] = np.sqrt(weight_ji) * 5
                else:
                    # If nodes not directly connected, use a larger default distance
                    ideal_distances[i, j] = np.sqrt(100) * 5

        # Run force-directed placement
        temp = temperature
        for iteration in range(iterations):
            # Calculate forces
            forces = np.zeros((n_nodes, 2))

            # Calculate repulsive forces between all pairs of nodes
            for i in range(n_nodes):
                for j in range(n_nodes):
                    if i == j:
                        continue

                    # Vector from j to i
                    dx = positions[i, 0] - positions[j, 0]
                    dy = positions[i, 1] - positions[j, 1]

                    # Distance between nodes
                    distance = max(0.1, np.sqrt(dx ** 2 + dy ** 2))

                    # Repulsive force
                    k = 1.0  # Repulsion strength
                    f_rep = k / distance

                    # Normalize direction
                    dx /= distance
                    dy /= distance

                    # Add repulsive force
                    forces[i, 0] += dx * f_rep
                    forces[i, 1] += dy * f_rep

            # Calculate attractive forces for connected nodes
            for i, node_i in enumerate(nodes):
                for j, node_j in enumerate(nodes):
                    if i == j:
                        continue

                    # Check if nodes are connected
                    weight_ij = self.graph.get_edge_weight(node_i, node_j)
                    weight_ji = self.graph.get_edge_weight(node_j, node_i)

                    if weight_ij is not None or weight_ji is not None:
                        # Vector from i to j
                        dx = positions[j, 0] - positions[i, 0]
                        dy = positions[j, 1] - positions[i, 1]

                        # Distance between nodes
                        distance = max(0.1, np.sqrt(dx ** 2 + dy ** 2))

                        # Ideal distance based on edge weight
                        ideal = ideal_distances[i, j]

                        # Spring force
                        f_spring = (distance - ideal) / ideal

                        # Normalize direction
                        dx /= distance
                        dy /= distance

                        # Add attractive force
                        forces[i, 0] += dx * f_spring
                        forces[i, 1] += dy * f_spring

            # Update positions based on forces
            for i in range(n_nodes):
                # Apply temperature to limit movement
                dx = forces[i, 0] * temp
                dy = forces[i, 1] * temp

                # Limit maximum movement per iteration
                max_move = 20
                dx = max(-max_move, min(max_move, dx))
                dy = max(-max_move, min(max_move, dy))

                # Update position
                positions[i, 0] += dx
                positions[i, 1] += dy

                # Keep within canvas bounds
                positions[i, 0] = max(0, min(self.canvas_width, positions[i, 0]))
                positions[i, 1] = max(0, min(self.canvas_height, positions[i, 1]))

            # Cool down temperature
            temp *= cooling_factor

            # Log progress
            if iteration % 100 == 0:
                self.logger.debug(f"Force-directed placement: iteration {iteration}/{iterations}")

        # Update graph with coordinates
        for i, node in enumerate(nodes):
            x, y = positions[i]
            self.graph.set_node_coordinates(node, x, y)

        self.logger.info("Coordinate generation complete.")
        return True

    def generate_simple_coordinates(self):
        """
        Generate simple coordinates based on a circle layout.
        Useful when force-directed placement is too complex or doesn't converge well.

        Returns:
            bool: True if coordinates were generated successfully
        """
        self.logger.info("Generating simple circle layout coordinates...")

        # Get all nodes
        nodes = list(self.graph.adjacency_list.keys())
        if not nodes:
            self.logger.error("No nodes in graph. Cannot generate coordinates.")
            return False

        n_nodes = len(nodes)

        # Calculate center of canvas
        center_x = self.canvas_width / 2
        center_y = self.canvas_height / 2

        # Calculate radius
        radius = min(self.canvas_width, self.canvas_height) * 0.4

        # Assign positions in a circle
        for i, node in enumerate(nodes):
            angle = 2 * np.pi * i / n_nodes
            x = center_x + radius * np.cos(angle)
            y = center_y + radius * np.sin(angle)

            self.graph.set_node_coordinates(node, x, y)

        self.logger.info("Simple coordinate generation complete.")
        return True

    def adjust_coordinates_by_department_type(self, department_types=None):
        """
        Adjust coordinates to group departments of similar types.
        This is a heuristic approach to make the layout more realistic.

        Args:
            department_types: Dictionary mapping department names to type categories.
                             If None, will try to infer from department names.

        Returns:
            bool: True if coordinates were adjusted successfully
        """
        self.logger.info("Adjusting coordinates by department type...")

        # Get all nodes
        nodes = list(self.graph.adjacency_list.keys())
        if not nodes:
            self.logger.error("No nodes in graph. Cannot adjust coordinates.")
            return False

            # If department types not provided, try to infer from names
        if department_types is None:
            department_types = self._infer_department_types(nodes)

            # Group nodes by type
        type_groups = {}
        for node, dept_type in department_types.items():
            if dept_type not in type_groups:
                type_groups[dept_type] = []
            type_groups[dept_type].append(node)

        # Calculate current centroid of the layout
        centroid_x = 0
        centroid_y = 0
        for node in nodes:
            x, y = self.graph.get_node_coordinates(node)
            centroid_x += x
            centroid_y += y
        centroid_x /= len(nodes)
        centroid_y /= len(nodes)

        # Assign "regions" to each department type
        # We divide the canvas into sections for different department types
        num_types = len(type_groups)
        type_regions = {}

        # Simple case: place different types in different regions
        if num_types <= 4:
            # Four quadrants
            regions = [
                (self.canvas_width * 0.25, self.canvas_height * 0.25),  # Top left
                (self.canvas_width * 0.75, self.canvas_height * 0.25),  # Top right
                (self.canvas_width * 0.25, self.canvas_height * 0.75),  # Bottom left
                (self.canvas_width * 0.75, self.canvas_height * 0.75),  # Bottom right
            ]

            for i, dept_type in enumerate(type_groups.keys()):
                type_regions[dept_type] = regions[i]
        else:
            # More complex: arrange in a circle
            radius = min(self.canvas_width, self.canvas_height) * 0.3
            for i, dept_type in enumerate(type_groups.keys()):
                angle = 2 * np.pi * i / num_types
                x = self.canvas_width / 2 + radius * np.cos(angle)
                y = self.canvas_height / 2 + radius * np.sin(angle)
                type_regions[dept_type] = (x, y)

        # Move departments toward their type's region
        adjustment_factor = 0.3  # How strongly to pull toward region
        for dept_type, region_center in type_regions.items():
            for node in type_groups.get(dept_type, []):
                x, y = self.graph.get_node_coordinates(node)

                # Calculate vector toward region center
                dx = region_center[0] - x
                dy = region_center[1] - y

                # Apply adjustment
                new_x = x + dx * adjustment_factor
                new_y = y + dy * adjustment_factor

                # Update coordinates
                self.graph.set_node_coordinates(node, new_x, new_y)

        self.logger.info("Coordinate adjustment by department type complete.")
        return True

    def _infer_department_types(self, nodes):
        """
        Attempt to infer department types from their names.
        This is a heuristic approach using common keywords.

        Args:
            nodes: List of department names

        Returns:
            dict: Dictionary mapping department names to inferred types
        """
        # Define common keywords for different department types
        type_keywords = {
            'Emergency': ['emergency', 'er', 'trauma', 'acute'],
            'Surgery': ['surgery', 'surgical', 'operating', 'operation', 'or'],
            'Inpatient': ['ward', 'inpatient', 'patient', 'bed', 'room', 'icu', 'intensive'],
            'Diagnostic': ['radiology', 'imaging', 'xray', 'x-ray', 'mri', 'ct', 'scan', 'diagnostic', 'lab',
                           'laboratory', 'pathology'],
            'Outpatient': ['clinic', 'outpatient', 'consultation', 'therapy'],
            'Support': ['pharmacy', 'supply', 'storage', 'kitchen', 'cafeteria', 'admin', 'office', 'reception',
                        'entrance', 'lounge']
        }

        # Default type
        default_type = 'Other'

        # Map nodes to types
        node_types = {}
        for node in nodes:
            node_lower = node.lower()

            for dept_type, keywords in type_keywords.items():
                if any(keyword in node_lower for keyword in keywords):
                    node_types[node] = dept_type
                    break
            else:
                node_types[node] = default_type

        return node_types

    def apply_jitter(self, amount=10):
        """
        Apply small random offsets to coordinates to avoid perfect overlaps.

        Args:
            amount: Maximum jitter amount in pixels

        Returns:
            bool: True if jitter was applied successfully
        """
        self.logger.info(f"Applying coordinate jitter (max {amount} pixels)...")

        # Get all nodes
        nodes = list(self.graph.adjacency_list.keys())
        if not nodes:
            self.logger.error("No nodes in graph. Cannot apply jitter.")
            return False

        # Apply jitter to each node
        for node in nodes:
            x, y = self.graph.get_node_coordinates(node)

            # Add small random offsets
            x += random.uniform(-amount, amount)
            y += random.uniform(-amount, amount)

            # Keep within canvas bounds
            x = max(0, min(self.canvas_width, x))
            y = max(0, min(self.canvas_height, y))

            # Update coordinates
            self.graph.set_node_coordinates(node, x, y)

        self.logger.info("Coordinate jitter applied.")
        return True

    def export_coordinates(self, output_file=None):
        """
        Export node coordinates to a file.

        Args:
            output_file: Path to output file. If None, returns coordinate dict.

        Returns:
            dict or bool: Dictionary of coordinates if output_file is None, else True on success
        """
        # Get all nodes
        nodes = list(self.graph.adjacency_list.keys())
        if not nodes:
            self.logger.error("No nodes in graph. Cannot export coordinates.")
            return False if output_file else {}

        # Collect coordinates
        coordinates = {}
        for node in nodes:
            coordinates[node] = self.graph.get_node_coordinates(node)

        # Return or write to file
        if output_file is None:
            return coordinates

        try:
            import json
            with open(output_file, 'w') as f:
                json.dump(coordinates, f, indent=2)
            self.logger.info(f"Coordinates exported to {output_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting coordinates: {str(e)}")
            return False