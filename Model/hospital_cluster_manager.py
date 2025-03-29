# Model/hospital_cluster_manager.py
"""
Class for managing clustering of hospital departments.
Used for both visualization and optimization.
"""
import logging
import numpy as np
import random
from copy import deepcopy


class HospitalClusterManager:
    """Manages clustering of hospital departments for visualization and optimization."""

    def __init__(self, hospital, num_clusters=20):
        """
        Initialize the cluster manager.

        Args:
            hospital: Hospital instance with graph
            num_clusters: Target number of clusters to generate
        """
        self.hospital = hospital
        self.num_clusters = min(num_clusters, len(hospital.departments))
        self.clusters = {}  # cluster_id -> list of departments
        self.department_to_cluster = {}  # department -> cluster_id
        self.cluster_metadata = {}  # Additional info (name, center, etc.)
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a logger for the HospitalClusterManager."""
        logger = logging.getLogger("HospitalClusterManager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def generate_clusters(self, method="kmeans"):
        """
        Generate clusters using specified method.

        Args:
            method: Clustering method ("kmeans", "hierarchical", or "department_type")

        Returns:
            dict: The generated clusters
        """
        self.logger.info(f"Generating {self.num_clusters} clusters using {method} method")

        if method == "kmeans":
            self._kmeans_clustering()
        elif method == "hierarchical":
            self._hierarchical_clustering()
        elif method == "department_type":
            self._department_type_clustering()
        else:
            self.logger.warning(f"Unknown clustering method: {method}, falling back to k-means")
            self._kmeans_clustering()

        self._calculate_cluster_metadata()

        # Validate clusters
        self._validate_clusters()

        return self.clusters

    def _validate_clusters(self):
        """Ensure all departments are assigned to clusters."""
        # Check if all departments have a cluster
        assigned_depts = set()
        for cluster_depts in self.clusters.values():
            assigned_depts.update(cluster_depts)

        all_depts = set(self.hospital.departments)
        unassigned = all_depts - assigned_depts

        if unassigned:
            self.logger.warning(f"Found {len(unassigned)} unassigned departments. Assigning to nearest clusters.")
            self._assign_unassigned_departments(unassigned)

        # Update department_to_cluster mapping
        self.department_to_cluster = {}
        for cluster_id, depts in self.clusters.items():
            for dept in depts:
                self.department_to_cluster[dept] = cluster_id

    def _assign_unassigned_departments(self, unassigned_depts):
        """Assign any unassigned departments to the nearest cluster."""
        if not self.clusters:
            # If no clusters exist, create one with all departments
            self.clusters["cluster_0"] = list(unassigned_depts)
            return

        # Calculate cluster centers
        cluster_centers = {}
        for cluster_id, depts in self.clusters.items():
            if not depts:
                continue

            # Calculate average coordinates
            coords = []
            for dept in depts:
                try:
                    x, y = self.hospital.graph.get_node_coordinates(dept)
                    coords.append((x, y))
                except (KeyError, ValueError):
                    continue

            if coords:
                avg_x = sum(x for x, y in coords) / len(coords)
                avg_y = sum(y for x, y in coords) / len(coords)
                cluster_centers[cluster_id] = (avg_x, avg_y)

        # Assign each unassigned department to the nearest cluster
        for dept in unassigned_depts:
            try:
                dept_x, dept_y = self.hospital.graph.get_node_coordinates(dept)

                # Find nearest cluster
                nearest_cluster = None
                min_distance = float('inf')

                for cluster_id, (center_x, center_y) in cluster_centers.items():
                    distance = ((dept_x - center_x) ** 2 + (dept_y - center_y) ** 2) ** 0.5

                    if distance < min_distance:
                        min_distance = distance
                        nearest_cluster = cluster_id

                if nearest_cluster:
                    self.clusters[nearest_cluster].append(dept)
                else:
                    # If no nearest cluster found, add to first cluster
                    first_cluster = next(iter(self.clusters.keys()))
                    self.clusters[first_cluster].append(dept)

            except (KeyError, ValueError):
                # If coordinates not found, add to first cluster
                first_cluster = next(iter(self.clusters.keys()))
                self.clusters[first_cluster].append(dept)

    def _kmeans_clustering(self):
        """
        Perform K-means clustering on hospital departments based on coordinates.
        """
        departments = self.hospital.departments
        if not departments:
            self.logger.warning("No departments found for clustering")
            return

        # Get coordinates for all departments
        coordinates = {}
        for dept in departments:
            try:
                x, y = self.hospital.graph.get_node_coordinates(dept)
                coordinates[dept] = (x, y)
            except (KeyError, ValueError):
                self.logger.warning(f"Coordinates not found for {dept}, using (0,0)")
                coordinates[dept] = (0, 0)

        # Initialize centroids using k-means++ approach
        centroids = self._initialize_centroids(list(coordinates.values()))

        # Run K-means for a fixed number of iterations
        max_iterations = 100
        clusters = [[] for _ in range(len(centroids))]

        for iteration in range(max_iterations):
            # Clear current clusters
            new_clusters = [[] for _ in range(len(centroids))]

            # Assign each department to nearest centroid
            for dept, coord in coordinates.items():
                min_dist = float('inf')
                closest_cluster = 0

                for i, centroid in enumerate(centroids):
                    dist = ((coord[0] - centroid[0]) ** 2 + (coord[1] - centroid[1]) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        closest_cluster = i

                new_clusters[closest_cluster].append(dept)

            # Check if clusters have changed
            if all(set(old) == set(new) for old, new in zip(clusters, new_clusters) if old and new):
                self.logger.debug(f"K-means converged after {iteration + 1} iterations")
                clusters = new_clusters
                break

            clusters = new_clusters

            # Update centroids
            for i in range(len(centroids)):
                if clusters[i]:
                    cluster_coords = [coordinates[dept] for dept in clusters[i]]
                    centroids[i] = (
                        sum(x for x, y in cluster_coords) / len(cluster_coords),
                        sum(y for x, y in cluster_coords) / len(cluster_coords)
                    )

        # Store the resulting clusters
        for i, cluster_depts in enumerate(clusters):
            if cluster_depts:  # Skip empty clusters
                self.clusters[f"cluster_{i}"] = cluster_depts

    def _initialize_centroids(self, coordinates, method="kmeans++"):
        """
        Initialize centroids for K-means clustering.

        Args:
            coordinates: List of (x, y) coordinates
            method: Initialization method ("random" or "kmeans++")

        Returns:
            list: Initial centroids
        """
        if not coordinates:
            return []

        if method == "random":
            # Random selection
            indices = random.sample(range(len(coordinates)), min(self.num_clusters, len(coordinates)))
            return [coordinates[i] for i in indices]
        else:
            # K-means++ method (select centroids to maximize minimum distance)
            centroids = [random.choice(coordinates)]

            while len(centroids) < min(self.num_clusters, len(coordinates)):
                # Calculate distances to nearest centroid for each point
                distances = []
                for coord in coordinates:
                    min_dist = min(((coord[0] - c[0]) ** 2 + (coord[1] - c[1]) ** 2) ** 0.5 for c in centroids)
                    distances.append(min_dist)

                # Select the point with the highest distance
                max_dist_idx = distances.index(max(distances))
                centroids.append(coordinates[max_dist_idx])

            return centroids

    def _hierarchical_clustering(self):
        """
        Perform hierarchical clustering on hospital departments.
        """
        departments = self.hospital.departments
        if not departments:
            self.logger.warning("No departments found for clustering")
            return

        # Get coordinates for all departments
        coordinates = {}
        for dept in departments:
            try:
                x, y = self.hospital.graph.get_node_coordinates(dept)
                coordinates[dept] = (x, y)
            except (KeyError, ValueError):
                self.logger.warning(f"Coordinates not found for {dept}, using (0,0)")
                coordinates[dept] = (0, 0)

        # Start with each department in its own cluster
        clusters = [[dept] for dept in departments]

        # Calculate distances between all pairs of departments
        distances = {}
        for i, dept1 in enumerate(departments):
            for j, dept2 in enumerate(departments):
                if i < j:  # Only calculate distances once per pair
                    coord1 = coordinates[dept1]
                    coord2 = coordinates[dept2]
                    dist = ((coord1[0] - coord2[0]) ** 2 + (coord1[1] - coord2[1]) ** 2) ** 0.5
                    distances[(dept1, dept2)] = dist

        # Merge until we have the desired number of clusters
        while len(clusters) > self.num_clusters:
            # Find the two closest clusters
            min_dist = float('inf')
            closest_pair = (0, 1)

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    # Calculate average distance between all pairs of departments in the two clusters
                    cluster_dist = 0
                    pair_count = 0

                    for dept1 in clusters[i]:
                        for dept2 in clusters[j]:
                            key = (dept1, dept2) if (dept1, dept2) in distances else (dept2, dept1)
                            if key in distances:
                                cluster_dist += distances[key]
                                pair_count += 1

                    # Average distance
                    avg_dist = cluster_dist / max(1, pair_count)

                    if avg_dist < min_dist:
                        min_dist = avg_dist
                        closest_pair = (i, j)

            # Merge the closest clusters
            i, j = closest_pair
            clusters[i].extend(clusters[j])
            clusters.pop(j)

        # Store the resulting clusters
        for i, cluster_depts in enumerate(clusters):
            self.clusters[f"cluster_{i}"] = cluster_depts

    def _department_type_clustering(self):
        """
        Cluster departments based on their inferred types and proximity.
        This approach tends to create more semantically meaningful clusters.
        """
        departments = self.hospital.departments
        if not departments:
            self.logger.warning("No departments found for clustering")
            return

        # Infer department types
        dept_types = self._infer_department_types(departments)

        # Group departments by type
        type_groups = {}
        for dept, dept_type in dept_types.items():
            if dept_type not in type_groups:
                type_groups[dept_type] = []
            type_groups[dept_type].append(dept)

        # Get coordinates for all departments
        coordinates = {}
        for dept in departments:
            try:
                x, y = self.hospital.graph.get_node_coordinates(dept)
                coordinates[dept] = (x, y)
            except (KeyError, ValueError):
                coordinates[dept] = (0, 0)

        # Initialize clusters
        cluster_id = 0

        # For each department type, create one or more clusters
        for dept_type, depts in type_groups.items():
            # Skip if no departments of this type
            if not depts:
                continue

            # Determine how many clusters to create for this type based on size
            num_type_clusters = max(1, min(len(depts) // 5, self.num_clusters // len(type_groups)))

            if len(depts) <= num_type_clusters:
                # If few departments, put each in its own cluster
                for dept in depts:
                    self.clusters[f"cluster_{cluster_id}"] = [dept]
                    cluster_id += 1
            elif num_type_clusters == 1:
                # If only one cluster needed, keep all together
                self.clusters[f"cluster_{cluster_id}"] = depts
                cluster_id += 1
            else:
                # Otherwise, use k-means to create subclusters
                subclusters = self._subcluster_by_kmeans(depts, coordinates, num_type_clusters)

                for subcluster in subclusters:
                    if subcluster:  # Skip empty subclusters
                        self.clusters[f"cluster_{cluster_id}"] = subcluster
                        cluster_id += 1

        # If we have too many clusters, merge the smallest ones
        while len(self.clusters) > self.num_clusters:
            # Find the smallest cluster
            smallest_cluster = min(self.clusters.items(), key=lambda x: len(x[1]))
            smallest_id = smallest_cluster[0]
            smallest_depts = smallest_cluster[1]

            # Find the nearest cluster to merge with
            nearest_cluster = None
            min_distance = float('inf')

            for cluster_id, cluster_depts in self.clusters.items():
                if cluster_id == smallest_id:
                    continue

                # Calculate average distance between clusters
                total_dist = 0
                pair_count = 0

                for dept1 in smallest_depts:
                    if dept1 not in coordinates:
                        continue

                    for dept2 in cluster_depts:
                        if dept2 not in coordinates:
                            continue

                        x1, y1 = coordinates[dept1]
                        x2, y2 = coordinates[dept2]
                        dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

                        total_dist += dist
                        pair_count += 1

                if pair_count > 0:
                    avg_dist = total_dist / pair_count

                    if avg_dist < min_distance:
                        min_distance = avg_dist
                        nearest_cluster = cluster_id

            # Merge with nearest cluster
            if nearest_cluster:
                self.clusters[nearest_cluster].extend(smallest_depts)
                del self.clusters[smallest_id]
            else:
                # If no suitable merge found, stop merging
                break

    def _subcluster_by_kmeans(self, departments, coordinates, num_clusters):
        """
        Create subclusters for departments of the same type using k-means.

        Args:
            departments: List of departments to cluster
            coordinates: Dictionary mapping departments to (x, y) coordinates
            num_clusters: Number of subclusters to create

        Returns:
            list: List of department lists (subclusters)
        """
        # Get coordinates for these departments
        dept_coords = []
        for dept in departments:
            if dept in coordinates:
                dept_coords.append((dept, coordinates[dept]))

        if not dept_coords:
            return [[]]

        # Initialize centroids using k-means++
        centroid_indices = [0]  # Start with the first department

        while len(centroid_indices) < min(num_clusters, len(dept_coords)):
            # Calculate distances to nearest centroid for each point
            max_dist = -1
            max_idx = -1

            for i, (_, coord) in enumerate(dept_coords):
                if i in centroid_indices:
                    continue

                # Find distance to nearest centroid
                min_cent_dist = float('inf')
                for cent_idx in centroid_indices:
                    cent_coord = dept_coords[cent_idx][1]
                    dist = ((coord[0] - cent_coord[0]) ** 2 + (coord[1] - cent_coord[1]) ** 2) ** 0.5
                    min_cent_dist = min(min_cent_dist, dist)

                # Keep track of the point with the maximum minimum distance
                if min_cent_dist > max_dist:
                    max_dist = min_cent_dist
                    max_idx = i

            if max_idx >= 0:
                centroid_indices.append(max_idx)

        # Initial centroids
        centroids = [dept_coords[i][1] for i in centroid_indices]

        # Run k-means
        subclusters = [[] for _ in range(len(centroids))]

        # Assign departments to nearest centroid
        for dept, coord in dept_coords:
            min_dist = float('inf')
            nearest_idx = 0

            for i, centroid in enumerate(centroids):
                dist = ((coord[0] - centroid[0]) ** 2 + (coord[1] - centroid[1]) ** 2) ** 0.5

                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = i

            subclusters[nearest_idx].append(dept)

        return subclusters

    def _calculate_cluster_metadata(self):
        """
        Calculate additional metadata for each cluster.
        - Center position
        - Name based on dominant department type
        - Size (number of departments)
        """
        for cluster_id, departments in self.clusters.items():
            # Skip empty clusters
            if not departments:
                continue

            # Calculate center position
            coords = []
            for dept in departments:
                try:
                    x, y = self.hospital.graph.get_node_coordinates(dept)
                    coords.append((x, y))
                except (KeyError, ValueError):
                    continue

            if coords:
                avg_x = sum(x for x, y in coords) / len(coords)
                avg_y = sum(y for x, y in coords) / len(coords)
            else:
                avg_x, avg_y = 0, 0

            # Determine cluster name based on dominant department type
            dept_types = self._infer_department_types(departments)
            type_counts = {}

            for dept_type in dept_types.values():
                type_counts[dept_type] = type_counts.get(dept_type, 0) + 1

            if type_counts:
                most_common_type = max(type_counts.items(), key=lambda x: x[1])[0]
            else:
                most_common_type = "Other"

            # Create metadata
            self.cluster_metadata[cluster_id] = {
                "center": (avg_x, avg_y),
                "name": f"{most_common_type} Area",
                "size": len(departments),
                "dominant_type": most_common_type,
                "departments": departments
            }

    def _infer_department_types(self, departments):
        """
        Attempt to infer department types from their names.
        This is a heuristic approach using common keywords.

        Args:
            departments: List of department names

        Returns:
            dict: Dictionary mapping department names to inferred types
        """
        # Define common keywords for different department types
        type_keywords = {
            'Emergency': ['emergency', 'er', 'trauma', 'acute', 'resuscitation'],
            'Surgery': ['surgery', 'surgical', 'operating', 'operation', 'or', 'theater'],
            'Inpatient': ['ward', 'inpatient', 'patient', 'bed', 'room', 'icu', 'intensive',
                          'care', 'cardiac', 'neuro', 'burn'],
            'Diagnostic': ['radiology', 'imaging', 'xray', 'x-ray', 'mri', 'ct', 'scan',
                           'diagnostic', 'lab', 'laboratory', 'pathology', 'blood', 'specimen'],
            'Outpatient': ['clinic', 'outpatient', 'consultation', 'therapy', 'rehab',
                           'rehabilitation', 'physical', 'occupational'],
            'Support': ['pharmacy', 'supply', 'storage', 'kitchen', 'cafeteria', 'admin',
                        'office', 'reception', 'entrance', 'lounge', 'security', 'maintenance']
        }

        # Special case for transporter lounge
        transporter_keywords = ['transporter', 'transport', 'lounge', 'dispatch']

        # Default type
        default_type = 'Other'

        # Map departments to types
        dept_types = {}
        for dept in departments:
            dept_lower = dept.lower()

            # Special case for transporter lounge
            if any(keyword in dept_lower for keyword in transporter_keywords):
                dept_types[dept] = 'Support'
                continue

            # Check each department type
            for dept_type, keywords in type_keywords.items():
                if any(keyword in dept_lower for keyword in keywords):
                    dept_types[dept] = dept_type
                    break
            else:
                dept_types[dept] = default_type

        return dept_types

    def get_cluster_for_department(self, department):
        """
        Get the cluster ID for a department.

        Args:
            department: Department name

        Returns:
            str: Cluster ID or None if not found
        """
        return self.department_to_cluster.get(department)

    def get_departments_in_cluster(self, cluster_id):
        """
        Get all departments in a cluster.

        Args:
            cluster_id: Cluster ID

        Returns:
            list: List of department names
        """
        return self.clusters.get(cluster_id, [])

    #