import numpy as np
import time
import logging
from copy import deepcopy
from Model.Assignment_strategies.ILP.ilp_makespan import ILPMakespan


class ClusterBasedILP:
    """
    Clustered ILP Optimizer for hospital transport assignment.
    Divides departments into geographic clusters and solves each independently.

    Advanced Features:
    - Adaptive clustering based on hospital size
    - Multiple clustering methods (k-means, hierarchical)
    - Performance tracking and metrics
    - Detailed logging
    - Fallback mechanisms
    """

    def __init__(self, transporters, requests, graph, num_clusters=None,
                 clustering_method="kmeans", debug_mode=False, time_limit=30):
        """
        Initialize the clustered ILP optimizer.

        Args:
            transporters: List of transporter objects
            requests: List of transport request objects
            graph: Hospital graph with department locations
            num_clusters: Number of clusters (None for auto-determination)
            clustering_method: Method to use for clustering ("kmeans" or "hierarchical")
            debug_mode: Enable detailed logging
            time_limit: Maximum time in seconds for optimization
        """
        self.transporters = transporters
        self.requests = requests
        self.graph = graph
        self.clustering_method = clustering_method
        self.debug_mode = debug_mode
        self.time_limit = time_limit

        # Performance metrics
        self.preprocessing_time = 0
        self.clustering_time = 0
        self.solving_time = 0
        self.total_time = 0

        # Internal state
        self.clusters = []
        self.cluster_requests = []
        self.transporter_clusters = []
        self.cluster_plans = {}

        # Setup logging
        self._setup_logging()

        # Auto-determine number of clusters if not specified
        if num_clusters is None:
            self.num_clusters = self._determine_cluster_count()
        else:
            self.num_clusters = num_clusters

        # Ensure we don't have more clusters than transporters
        self.num_clusters = min(self.num_clusters, len(self.transporters)) if self.transporters else 2

        self.logger.debug(f"Initialized ClusterBasedILP with {self.num_clusters} clusters using "
                          f"{self.clustering_method} method")

    def _setup_logging(self):
        """Set up logging for the optimizer."""
        self.logger = logging.getLogger('ClusterBasedILP')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)

    def _determine_cluster_count(self):
        """
        Automatically determine the optimal number of clusters based on hospital size.

        Returns:
            int: Recommended number of clusters
        """
        # Get unique departments involved in requests
        departments = set()
        for r in self.requests:
            departments.add(r.origin)
            departments.add(r.destination)

        # Scale clusters based on department count
        dept_count = len(departments)
        self.logger.debug(f"Auto-determining clusters for {dept_count} departments")

        if dept_count <= 8:
            return 2  # Very small hospital
        elif dept_count <= 15:
            return 3  # Small hospital
        elif dept_count <= 30:
            return 4  # Medium hospital
        elif dept_count <= 60:
            return 5  # Large hospital
        elif dept_count <= 100:
            return max(5, dept_count // 15)  # Very large hospital (1 cluster per ~15 depts)
        else:
            return max(7, dept_count // 20)  # Enormous hospital (1 cluster per ~20 depts)

    def build_and_solve(self):
        """
        Generate an assignment plan using clustered ILP approach.

        Returns:
            dict: Assignment plan mapping transporter names to lists of requests
        """
        start_time = time.time()

        # If few requests or transporters, use standard ILP directly
        if len(self.requests) <= 15 or len(self.transporters) <= 3:
            self.logger.info("Small problem detected, using standard ILP solver")
            return self._solve_with_standard_ilp()

        # Process and cluster the hospital
        preprocess_start = time.time()
        self._preprocess_data()
        self.preprocessing_time = time.time() - preprocess_start

        # Generate department clusters
        cluster_start = time.time()
        self._generate_clusters()
        self.clustering_time = time.time() - cluster_start

        # Assign requests to clusters
        self._assign_requests_to_clusters()

        # Assign transporters to clusters
        self._assign_transporters_to_clusters()

        # Check if clustering was effective
        if self._check_clustering_effectiveness() is False:
            self.logger.warning("Clustering was ineffective, reverting to standard ILP")
            return self._solve_with_standard_ilp()

        # Solve each cluster independently using standard ILP
        solve_start = time.time()
        master_plan = self._solve_clusters()
        self.solving_time = time.time() - solve_start

        # Post-process the solution (sorting, balancing)
        master_plan = self._post_process_solution(master_plan)

        self.total_time = time.time() - start_time
        self._log_performance_metrics()

        return master_plan

    def _preprocess_data(self):
        """Preprocess data for clustering (extract departments, coordinates, etc.)."""
        self.logger.debug("Preprocessing data for clustering")

        # Extract all unique departments from requests
        self.all_departments = set()
        for r in self.requests:
            self.all_departments.add(r.origin)
            self.all_departments.add(r.destination)

        # Create a map of department coordinates
        self.department_coords = {}
        for dept in self.all_departments:
            x, y = self.graph.get_node_coordinates(dept)
            self.department_coords[dept] = (x, y)

        # Create a distance matrix for departments
        self._create_distance_matrix()

        self.logger.debug(f"Preprocessing complete. Found {len(self.all_departments)} unique departments")

    def _create_distance_matrix(self):
        """Create a matrix of distances between all departments."""
        departments = list(self.all_departments)
        n = len(departments)
        self.distance_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                dept1, dept2 = departments[i], departments[j]
                distance = self._calculate_distance(dept1, dept2)
                self.distance_matrix[i, j] = distance
                self.distance_matrix[j, i] = distance

    def _calculate_distance(self, dept1, dept2):
        """Calculate the distance between two departments."""
        # Try using graph-based distance first
        try:
            path, _ = self.transporters[0].pathfinder.dijkstra(dept1, dept2)
            path_distance = sum(
                self.graph.get_edge_weight(path[i], path[i + 1])
                for i in range(len(path) - 1)
            )
            return path_distance
        except (IndexError, AttributeError, ValueError):
            # Fall back to Euclidean distance
            x1, y1 = self.department_coords[dept1]
            x2, y2 = self.department_coords[dept2]
            return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def _generate_clusters(self):
        """Generate clusters of departments based on selected method."""
        self.logger.info(f"Generating {self.num_clusters} clusters using {self.clustering_method} method")

        if self.clustering_method == "kmeans":
            self.clusters = self._kmeans_clustering()
        elif self.clustering_method == "hierarchical":
            self.clusters = self._hierarchical_clustering()
        else:
            self.logger.warning(f"Unknown clustering method: {self.clustering_method}, falling back to k-means")
            self.clusters = self._kmeans_clustering()

        # Filter out empty clusters
        self.clusters = [c for c in self.clusters if c]

        # Log cluster sizes
        for i, cluster in enumerate(self.clusters):
            self.logger.debug(f"Cluster {i + 1} has {len(cluster)} departments")

    def _kmeans_clustering(self):
        """
        Perform K-means clustering on hospital departments.

        Returns:
            list: List of clusters, where each cluster is a list of department names
        """
        departments = list(self.all_departments)
        if not departments:
            return [[] for _ in range(self.num_clusters)]

        # Extract coordinates for clustering
        coordinates = [self.department_coords[d] for d in departments]

        # Initialize centroids using k-means++ like approach
        centroids = [coordinates[0]]

        # Initialize remaining centroids by maximizing minimum distance
        for _ in range(1, self.num_clusters):
            distances = []
            for point in coordinates:
                min_dist = min(np.sum((np.array(point) - np.array(centroid)) ** 2)
                               for centroid in centroids)
                distances.append(min_dist)

            if not distances:
                break

            # Choose the farthest point as the next centroid
            next_centroid_idx = np.argmax(distances)
            if next_centroid_idx < len(coordinates):
                centroids.append(coordinates[next_centroid_idx])

        # Initialize clusters
        clusters = [[] for _ in range(len(centroids))]

        # Run K-means for a fixed number of iterations
        max_iterations = 15

        for iteration in range(max_iterations):
            # Clear current clusters
            new_clusters = [[] for _ in range(len(centroids))]

            # Assign each department to nearest centroid
            for i, dept in enumerate(departments):
                if i >= len(coordinates):
                    continue

                min_dist = float('inf')
                closest_cluster = 0

                for j, centroid in enumerate(centroids):
                    dist = np.sum((np.array(coordinates[i]) - np.array(centroid)) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        closest_cluster = j

                new_clusters[closest_cluster].append(dept)

            # Check if clusters have changed
            if all(set(old) == set(new) for old, new in zip(clusters, new_clusters) if old and new):
                self.logger.debug(f"K-means converged after {iteration + 1} iterations")
                clusters = new_clusters
                break

            clusters = new_clusters

            # Update centroids
            for j in range(len(centroids)):
                if clusters[j]:
                    cluster_coords = [self.department_coords[d] for d in clusters[j]]
                    centroids[j] = np.mean(cluster_coords, axis=0)

        return clusters

    def _hierarchical_clustering(self):
        """
        Perform hierarchical clustering on hospital departments.

        Returns:
            list: List of clusters, where each cluster is a list of department names
        """
        departments = list(self.all_departments)
        if not departments:
            return [[] for _ in range(self.num_clusters)]

        # Start with each department in its own cluster
        clusters = [[dept] for dept in departments]

        # Merge until we have the desired number of clusters
        while len(clusters) > self.num_clusters:
            # Find the two closest clusters
            min_dist = float('inf')
            closest_pair = (0, 1)

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    dist = self._calculate_cluster_distance(clusters[i], clusters[j])
                    if dist < min_dist:
                        min_dist = dist
                        closest_pair = (i, j)

            # Merge the closest clusters
            i, j = closest_pair
            clusters[i].extend(clusters[j])
            clusters.pop(j)

        return clusters

    def _calculate_cluster_distance(self, cluster1, cluster2):
        """Calculate the average distance between all points in two clusters."""
        total_dist = 0
        count = 0

        for dept1 in cluster1:
            for dept2 in cluster2:
                total_dist += self._calculate_distance(dept1, dept2)
                count += 1

        return total_dist / max(1, count)

    def _assign_requests_to_clusters(self):
        """Assign requests to appropriate clusters."""
        self.logger.debug("Assigning requests to clusters")
        self.cluster_requests = [[] for _ in range(len(self.clusters))]

        for r in self.requests:
            # Try to find a cluster containing both origin and destination
            for i, cluster_depts in enumerate(self.clusters):
                if r.origin in cluster_depts and r.destination in cluster_depts:
                    self.cluster_requests[i].append(r)
                    break
            else:
                # If origin and destination are in different clusters,
                # assign to the cluster containing origin
                for i, cluster_depts in enumerate(self.clusters):
                    if r.origin in cluster_depts:
                        self.cluster_requests[i].append(r)
                        break
                else:
                    # Fallback: add to first cluster with departments
                    for i, cluster in enumerate(self.clusters):
                        if cluster:
                            self.cluster_requests[i].append(r)
                            break

        # Log request distribution
        for i, requests in enumerate(self.cluster_requests):
            self.logger.debug(f"Cluster {i + 1} has {len(requests)} requests")

    def _assign_transporters_to_clusters(self):
        """Assign transporters to clusters based on location and workload balance."""
        self.logger.debug("Assigning transporters to clusters")

        # Calculate workload per cluster
        cluster_workload = [sum(len(self._get_full_path(r)) for r in reqs)
                            for reqs in self.cluster_requests]

        # Normalize workload (avoid division by zero)
        total_workload = sum(cluster_workload) or 1
        normalized_workload = [w / total_workload for w in cluster_workload]

        # Calculate transporters per cluster (weighted by workload)
        transporters_per_cluster = []
        for i, workload in enumerate(normalized_workload):
            # At least 1 transporter if cluster has requests
            count = max(1 if self.cluster_requests[i] else 0,
                        round(workload * len(self.transporters)))
            transporters_per_cluster.append(count)

        # Balance transporter allocation to match total count
        self._balance_transporter_allocation(transporters_per_cluster)

        # Assign specific transporters to each cluster based on location
        self.transporter_clusters = [[] for _ in range(len(self.clusters))]
        remaining_transporters = list(self.transporters)

        # For each cluster, find closest transporters
        for i, cluster_size in enumerate(transporters_per_cluster):
            if cluster_size == 0 or not self.clusters[i]:
                continue

            # Calculate cluster center
            cluster_center = self._calculate_cluster_center(self.clusters[i])

            # Sort transporters by distance to cluster center
            sorted_transporters = sorted(
                remaining_transporters,
                key=lambda t: self._distance_to_point(t, cluster_center)
            )

            # Assign closest transporters to this cluster
            for j in range(min(cluster_size, len(sorted_transporters))):
                self.transporter_clusters[i].append(sorted_transporters[j])
                remaining_transporters.remove(sorted_transporters[j])

        # Log transporter assignment
        for i, transporters in enumerate(self.transporter_clusters):
            transporter_names = [t.name for t in transporters]
            self.logger.debug(f"Cluster {i + 1} assigned transporters: {transporter_names}")

    def _balance_transporter_allocation(self, transporters_per_cluster):
        """Balance the transporter allocation to match the total available transporters."""
        # Adjust if we have too many transporters assigned
        while sum(transporters_per_cluster) > len(self.transporters):
            # Find cluster with most transporters and reduce by 1
            idx = transporters_per_cluster.index(max(transporters_per_cluster))
            if transporters_per_cluster[idx] > 1:  # Don't go below 1 if there are requests
                transporters_per_cluster[idx] -= 1

        # Adjust if we have transporters left over
        while sum(transporters_per_cluster) < len(self.transporters):
            # Find the busiest cluster per transporter
            busiest_idx = -1
            max_workload_per_transporter = -1

            for i, count in enumerate(transporters_per_cluster):
                # Skip empty clusters
                if not self.clusters[i] or not self.cluster_requests[i]:
                    continue

                # Calculate workload per transporter
                if count > 0:  # Avoid division by zero
                    workload = len(self.cluster_requests[i]) / count
                    if workload > max_workload_per_transporter:
                        max_workload_per_transporter = workload
                        busiest_idx = i

            # If we found a busy cluster, add a transporter
            if busiest_idx != -1:
                transporters_per_cluster[busiest_idx] += 1
            else:
                # If no busy cluster found, just add to the first non-empty cluster
                for i, count in enumerate(transporters_per_cluster):
                    if self.clusters[i] and self.cluster_requests[i]:
                        transporters_per_cluster[i] += 1
                        break

    def _calculate_cluster_center(self, cluster):
        """Calculate the geometric center of a cluster."""
        if not cluster:
            return (0, 0)

        coords = [self.department_coords[dept] for dept in cluster]
        return np.mean(coords, axis=0)

    def _distance_to_point(self, transporter, point):
        """Calculate distance from a transporter's current location to a point."""
        try:
            tx, ty = self.graph.get_node_coordinates(transporter.current_location)
            return np.sqrt((tx - point[0]) ** 2 + (ty - point[1]) ** 2)
        except (AttributeError, KeyError):
            return float('inf')  # If location unknown, put at the end

    def _check_clustering_effectiveness(self):
        """
        Check if clustering was effective.

        Returns:
            bool: True if clustering seems effective, False otherwise
        """
        # Check if any cluster has no requests
        if any(not reqs for reqs in self.cluster_requests):
            self.logger.warning("Some clusters have no requests")

        # Check if any cluster has no transporters
        if any(not trans for trans in self.transporter_clusters):
            self.logger.warning("Some clusters have no transporters")

        # Check if clustering actually distributed the requests
        if len(self.clusters) <= 1:
            self.logger.warning("Only 1 cluster was created")
            return False

        # Check if one cluster has too many requests compared to others
        request_counts = [len(reqs) for reqs in self.cluster_requests]
        if request_counts:
            max_count = max(request_counts)
            if max_count > 0.8 * sum(request_counts):  # One cluster has >80% of requests
                self.logger.warning(
                    f"Unbalanced clustering: one cluster has {max_count} of {sum(request_counts)} requests")
                if sum(request_counts) < 20:  # Small problem, not worth clustering
                    return False

        return True

    def _solve_with_standard_ilp(self):
        """
        Solve the problem using the standard ILP approach.

        Returns:
            dict: Assignment plan
        """
        self.logger.info("Using standard ILP solver")
        standard_ilp = ILPMakespan(self.transporters, self.requests, self.graph)
        return standard_ilp.build_and_solve()

    def _solve_clusters(self):
        """
        Solve each cluster independently.

        Returns:
            dict: Combined assignment plan
        """
        self.logger.info(f"Solving {len(self.clusters)} clusters independently")

        master_plan = {t.name: [] for t in self.transporters}

        for i in range(len(self.clusters)):
            if not self.cluster_requests[i] or not self.transporter_clusters[i]:
                continue

            self.logger.debug(f"Solving cluster {i + 1} with {len(self.cluster_requests[i])} requests "
                              f"and {len(self.transporter_clusters[i])} transporters")

            # Create ILP for this cluster
            try:
                cluster_start = time.time()

                ilp = ILPMakespan(
                    self.transporter_clusters[i],
                    self.cluster_requests[i],
                    self.graph
                )

                # Solve with time limit
                cluster_plan = self._solve_with_timeout(ilp, self.time_limit / len(self.clusters))

                cluster_time = time.time() - cluster_start
                self.logger.debug(f"Cluster {i + 1} solved in {cluster_time:.2f} seconds")

                # Merge into master plan
                for t_name, t_requests in cluster_plan.items():
                    master_plan[t_name].extend(t_requests)

            except Exception as e:
                self.logger.error(f"Error solving cluster {i + 1}: {str(e)}")
                # If a cluster fails, we still continue with others

        return master_plan

    def _solve_with_timeout(self, ilp, timeout):
        """Solve an ILP with a timeout."""
        # Store original time limit if exists
        original_timeout = getattr(ilp, 'timeout', None)

        try:
            # Set timeout if the ILP solver supports it
            if hasattr(ilp, 'timeout'):
                ilp.timeout = timeout

            return ilp.build_and_solve()
        finally:
            # Restore original timeout
            if original_timeout is not None and hasattr(ilp, 'timeout'):
                ilp.timeout = original_timeout

    def _post_process_solution(self, plan):
        """
        Post-process the solution for better quality.

        Args:
            plan: Assignment plan

        Returns:
            dict: Improved assignment plan
        """
        # Sort each transporter's requests for efficient routes
        for t in self.transporters:
            if t.name in plan and plan[t.name]:
                plan[t.name] = self._sort_requests_by_greedy_chain(t, plan[t.name])

        # Check for workload balance
        self._balance_workload(plan)

        return plan

    def _balance_workload(self, plan):
        """
        Try to balance workload by moving requests between transporters.

        Args:
            plan: Assignment plan to balance
        """
        # Calculate current workload
        workloads = {}
        for t in self.transporters:
            requests = plan.get(t.name, [])
            workloads[t.name] = self._calculate_transporter_workload(t, requests)

        # Find max and min workload transporters
        if not workloads:
            return

        min_workload = min(workloads.values())
        max_workload = max(workloads.values())
        min_transporter = next(t.name for t in self.transporters if workloads.get(t.name) == min_workload)
        max_transporter = next(t.name for t in self.transporters if workloads.get(t.name) == max_workload)

        # If already balanced, do nothing
        imbalance = max_workload - min_workload
        if imbalance < 0.2 * max_workload:  # Less than 20% imbalance is acceptable
            return

        self.logger.debug(f"Workload imbalance detected: {min_workload:.2f} vs {max_workload:.2f}")

        # Try to move some requests from max to min
        max_requests = plan.get(max_transporter, [])

        # Sort requests by time (shortest first)
        max_requests_times = [(r, self._calculate_request_time(self._get_transporter_by_name(max_transporter), r))
                              for r in max_requests]
        sorted_requests = [r for r, _ in sorted(max_requests_times, key=lambda x: x[1])]

        # Try moving requests one by one
        for request in sorted_requests:
            # Check if moving this request would improve balance
            req_time = self._calculate_request_time(self._get_transporter_by_name(max_transporter), request)

            new_max = max_workload - req_time
            new_min = min_workload + self._calculate_request_time(
                self._get_transporter_by_name(min_transporter), request)

            # If it improves balance, move it
            if new_max >= new_min:  # Only move if it doesn't create a worse imbalance
                # Remove from max
                plan[max_transporter].remove(request)

                # Add to min
                if min_transporter not in plan:
                    plan[min_transporter] = []
                plan[min_transporter].append(request)

                # Update workloads
                workloads[max_transporter] = new_max
                workloads[min_transporter] = new_min
                max_workload = new_max
                min_workload = new_min

                # If balance is now acceptable, stop
                if max_workload - min_workload < 0.2 * max_workload:
                    break

    def _calculate_transporter_workload(self, transporter, requests):
        """Calculate total workload for a transporter with given requests."""
        if not requests:
            return 0

        total_time = 0
        current_location = transporter.current_location

        for request in requests:
            # Time to origin
            origin_time = self._calculate_path_time(current_location, request.origin)

            # Time to destination
            dest_time = self._calculate_path_time(request.origin, request.destination)

            total_time += origin_time + dest_time
            current_location = request.destination

        return total_time

    def _calculate_request_time(self, transporter, request):
        """Calculate time to handle a specific request by a specific transporter."""
        origin_time = self._calculate_path_time(transporter.current_location, request.origin)
        dest_time = self._calculate_path_time(request.origin, request.destination)
        return origin_time + dest_time

    def _calculate_path_time(self, start, end):
        """Calculate travel time between two points."""
        try:
            path, _ = self.transporters[0].pathfinder.dijkstra(start, end)
            return sum(
                self.graph.get_edge_weight(path[i], path[i + 1])
                for i in range(len(path) - 1)
            )
        except (IndexError, AttributeError, ValueError):
            # If path not found, estimate using coordinates
            try:
                x1, y1 = self.graph.get_node_coordinates(start)
                x2, y2 = self.graph.get_node_coordinates(end)
                # Rough estimate - Euclidean distance scaled by average graph edge weight
                dist = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                return dist / 10  # Scale factor (adjust based on your graph weights)
            except:
                return 10  # Default time if all else fails

    def _get_transporter_by_name(self, name):
        """Get a transporter object by name."""
        for t in self.transporters:
            if t.name == name:
                return t
        return None

    def _sort_requests_by_greedy_chain(self, transporter, requests):
        """Sort requests by a greedy chain to minimize travel time."""
        if not requests:
            return []

        remaining = deepcopy(requests)
        ordered = []
        current_location = transporter.current_location

        while remaining:
            # Find request whose origin is closest to current location
            next_request = min(
                remaining,
                key=lambda r: self._calculate_path_time(current_location, r.origin)
            )
            ordered.append(next_request)
            current_location = next_request.destination
            remaining.remove(next_request)

        return ordered

    def _get_full_path(self, request):
        """Get full path for a request (origin to destination)."""
        try:
            path, _ = self.transporters[0].pathfinder.dijkstra(request.origin, request.destination)
            return path
        except (IndexError, AttributeError, ValueError):
            return [request.origin, request.destination]

    def _log_performance_metrics(self):
        """Log performance metrics for the optimization process."""
        self.logger.info("Performance metrics:")
        self.logger.info(f"  Preprocessing time: {self.preprocessing_time:.2f}s")
        self.logger.info(f"  Clustering time: {self.clustering_time:.2f}s")
        self.logger.info(f"  Solving time: {self.solving_time:.2f}s")
        self.logger.info(f"  Total time: {self.total_time:.2f}s")

        # Calculate the proportion of time spent in each phase
        if self.total_time > 0:
            preproc_pct = 100 * self.preprocessing_time / self.total_time
            cluster_pct = 100 * self.clustering_time / self.total_time
            solve_pct = 100 * self.solving_time / self.total_time

            self.logger.info(f"  Time distribution: "
                             f"Preprocessing {preproc_pct:.1f}%, "
                             f"Clustering {cluster_pct:.1f}%, "
                             f"Solving {solve_pct:.1f}%")

    def estimate_travel_time(self, transporter, request):
        """
        Estimate travel time for a transporter to complete a request.

        Args:
            transporter: Transporter object
            request: Request object

        Returns:
            float: Estimated travel time in seconds
        """
        # Calculate time from current location to request origin
        to_origin_time = self._calculate_path_time(transporter.current_location, request.origin)

        # Calculate time from origin to destination
        to_dest_time = self._calculate_path_time(request.origin, request.destination)

        return to_origin_time + to_dest_time