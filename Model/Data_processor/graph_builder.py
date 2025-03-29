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
        self.name_mapping = {}  # Will store mapping from original names to normalized names

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

        # Step 1: Get all departments and normalize their names
        all_departments = self.analyzer.get_all_departments()
        normalized_departments, self.name_mapping = self._normalize_department_names(all_departments)

        # Step 2: Add normalized departments as nodes
        self._add_departments_as_nodes(normalized_departments)

        # Step 3: Prepare for edge creation with normalized names
        sorted_pairs = self._prepare_department_pairs_normalized()

        # Step 4: Create pathfinder for checking existing paths
        pathfinder = self._create_pathfinder()

        # Step 5: Add edges based on transport data
        self._add_edges_based_on_transport_data(sorted_pairs, pathfinder, path_threshold)

        return self.graph

    def _normalize_department_names(self, departments):
        """
        Normalize department names by grouping similar names together.

        Args:
            departments: List of original department names

        Returns:
            tuple: (normalized_names, name_mapping)
                - normalized_names: List of unique normalized department names
                - name_mapping: Dictionary mapping original names to normalized names
        """
        self.logger.info("Normalizing department names...")

        # Dictionary to map original names to normalized names
        name_mapping = {}

        # Group similar departments
        department_groups = {}

        for dept in departments:
            # Skip empty department names
            if not dept or dept.strip() == "":
                continue

            # Clean up the name (remove extra spaces, etc.)
            cleaned_name = dept.strip()

            # Find the best match among existing groups
            best_match = self._find_best_department_match(cleaned_name, department_groups.keys())

            if best_match:
                # Add to existing group
                department_groups[best_match].append(cleaned_name)
                name_mapping[cleaned_name] = best_match
            else:
                # Create new group
                department_groups[cleaned_name] = [cleaned_name]
                name_mapping[cleaned_name] = cleaned_name

        # Get unique normalized names
        normalized_names = list(department_groups.keys())

        # Log mapping for debugging
        for group_name, members in department_groups.items():
            if len(members) > 1:
                self.logger.info(f"Normalized group '{group_name}' contains {len(members)} variations:")
                for member in members:
                    self.logger.info(f"  - {member}")

        self.logger.info(f"Reduced {len(departments)} department names to {len(normalized_names)} unique departments")

        return normalized_names, name_mapping

    def _find_best_department_match(self, dept_name, existing_groups, threshold=0.7):
        """
        Find the best match for a department name among existing groups.

        Args:
            dept_name: Department name to match
            existing_groups: List of existing group names
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            str or None: Best matching group name or None if no good match
        """
        if not existing_groups:
            return None

        # Try exact prefix match first (more reliable for hospital departments)
        # Get the first few words (e.g., "Öron Näsa Hals")
        words = dept_name.split()
        if len(words) >= 2:
            prefix = " ".join(words[:min(3, len(words))])

            for group in existing_groups:
                group_words = group.split()
                if len(group_words) >= 2:
                    group_prefix = " ".join(group_words[:min(3, len(group_words))])

                    # If prefixes match, consider it the same department
                    if prefix.lower() == group_prefix.lower():
                        return group

        # If no prefix match, try more advanced similarity metrics
        best_match = None
        best_score = 0

        for group in existing_groups:
            # Calculate similarity score (various methods possible)
            score = self._calculate_name_similarity(dept_name, group)

            if score > threshold and score > best_score:
                best_score = score
                best_match = group

        return best_match

    def _calculate_name_similarity(self, name1, name2):
        """
        Calculate similarity between two department names.

        Args:
            name1: First department name
            name2: Second department name

        Returns:
            float: Similarity score (0.0-1.0)
        """
        # Convert to lowercase for comparison
        name1 = name1.lower()
        name2 = name2.lower()

        # Simple character-based similarity
        # Compute Jaccard similarity of character sets
        set1 = set(name1)
        set2 = set(name2)

        if not set1 or not set2:
            return 0

        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        char_similarity = intersection / union

        # Word-based similarity
        words1 = set(name1.split())
        words2 = set(name2.split())

        if not words1 or not words2:
            return char_similarity  # Fall back to char similarity

        word_intersection = len(words1.intersection(words2))
        word_union = len(words1.union(words2))

        word_similarity = word_intersection / word_union

        # Combined score (weighted more toward word similarity)
        return 0.3 * char_similarity + 0.7 * word_similarity

    def _add_departments_as_nodes(self, departments=None):
        """
        Add departments as nodes in the graph.

        Args:
            departments: List of department names. If None, fetches from analyzer.
        """
        if departments is None:
            departments = self.analyzer.get_all_departments()

        for dept in departments:
            self.graph.add_node(dept)

        self.logger.info(f"Added {len(departments)} nodes to the graph")

    def _prepare_department_pairs_normalized(self):
        """
        Prepare normalized department pairs sorted by transport time.

        Returns:
            list: Sorted list of ((origin, dest), time) tuples with normalized names
        """
        # Get median transport times between departments
        original_median_times = self.analyzer.get_median_transport_times()

        # Normalize department names in transport times
        normalized_median_times = {}

        for (orig_origin, orig_dest), time in original_median_times.items():
            # Map original names to normalized names
            norm_origin = self.name_mapping.get(orig_origin, orig_origin)
            norm_dest = self.name_mapping.get(orig_dest, orig_dest)

            # Skip if same department after normalization
            if norm_origin == norm_dest:
                continue

            # If there are multiple paths between the same normalized departments,
            # take the minimum time (fastest path)
            key = (norm_origin, norm_dest)
            if key in normalized_median_times:
                normalized_median_times[key] = min(normalized_median_times[key], time)
            else:
                normalized_median_times[key] = time

        # Create a sorted list of department pairs by transport time
        return sorted(normalized_median_times.items(), key=lambda x: x[1])

    def _create_pathfinder(self):
        """
        Create a pathfinder for checking existing paths.

        Returns:
            Pathfinder: Initialized pathfinder object
        """

        # Create a temporary Hospital for the pathfinder
        class TempHospital:
            def __init__(self, graph):
                self.graph = graph

            def get_graph(self):
                return self.graph

        temp_hospital = TempHospital(self.graph)
        return Pathfinder(temp_hospital)

    def _add_edges_based_on_transport_data(self, sorted_pairs, pathfinder, path_threshold):
        """
        Add edges to the graph based on transport data and pathfinding.

        Args:
            sorted_pairs: Sorted list of ((origin, dest), time) tuples
            pathfinder: Pathfinder object for checking existing paths
            path_threshold: Threshold for adding direct edges
        """
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

                if self._should_add_direct_edge(path, distance, scaled_time, path_threshold):
                    self.graph.add_edge(origin, dest, scaled_time)
                    added_edges += 1
                    self._log_edge_addition(origin, dest, scaled_time, path, distance)
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

    def _should_add_direct_edge(self, path, distance, scaled_time, path_threshold):
        """
        Determine if a direct edge should be added between departments.

        Args:
            path: Current path between departments
            distance: Current path distance
            scaled_time: Expected travel time
            path_threshold: Threshold for adding direct edges

        Returns:
            bool: True if direct edge should be added
        """
        # If no path exists, add direct edge
        if not path or len(path) < 2:
            return True

        # If path is significantly longer than expected, add direct edge
        if distance > scaled_time * path_threshold:
            return True

        return False

    def _log_edge_addition(self, origin, dest, scaled_time, path, distance):
        """Log the addition of an edge with appropriate reason."""
        if not path or len(path) < 2:
            self.logger.debug(f"Added edge {origin} -> {dest} (time: {scaled_time:.1f}s) - No existing path")
        else:
            self.logger.debug(f"Added edge {origin} -> {dest} (time: {scaled_time:.1f}s) - "
                              f"Existing path too long ({distance:.1f}s vs {scaled_time:.1f}s)")

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
            # Normalize department names if mapping exists
            if hasattr(self, 'name_mapping'):
                origin = self.name_mapping.get(origin, origin)
                dest = self.name_mapping.get(dest, dest)

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