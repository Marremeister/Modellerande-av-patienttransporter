"""
Model component for benchmark functionality.
Updated to include new optimization strategies.
"""
import numpy as np
from Model.model_transportation_request import TransportationRequest
from Model.Assignment_strategies.ILP.ilp_optimizer_strategy import ILPOptimizerStrategy
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode
from Model.Assignment_strategies.Random.random_assignment_strategy import RandomAssignmentStrategy
from Model.Assignment_strategies.Genetic_algorithms.genetic_algorithm_strategy import GeneticAlgorithmStrategy


class BenchmarkModel:
    """Handles the data and algorithms for benchmarking different strategies."""

    def __init__(self, hospital_system):
        """
        Initialize the benchmark model with a reference to the hospital system.

        Args:
            hospital_system: The hospital system to benchmark
        """
        self.system = hospital_system
        self.scenarios = self._initialize_scenarios()

    def _initialize_scenarios(self):
        """
        Initialize default benchmark scenarios.

        Returns:
            dict: A dictionary of predefined scenarios
        """
        return {
            "Default Scenario": self._get_default_scenario(),
            "Emergency Heavy": self._get_emergency_scenario(),
            "Distributed": self._get_distributed_scenario(),
            "Complex": self._get_complex_benchmark()
        }

    def get_scenario(self, name):
        """Get a specific scenario by name."""
        return self.scenarios.get(name, self._get_default_scenario())

    def add_scenario(self, name, requests):
        """Add a new scenario to the available scenarios."""
        self.scenarios[name] = requests
        return self.scenarios

    def _get_default_scenario(self):
        """Default transport scenario with a mix of requests."""
        return [
            ("Emergency", "ICU", True),
            ("Reception", "Radiology", False),
            ("ICU", "General Ward", False),
            ("Cardiology", "Surgery", False),
            ("Pharmacy", "Neurology", False),
            ("Pediatrics", "Orthopedics", True),
            ("Admin Office", "Cafeteria", False),
            ("Radiology", "Laboratory", False),
            ("Emergency", "Surgery", True),
            ("Reception", "Cardiology", False)
        ]

    def _get_emergency_scenario(self):
        """Scenario focused on emergency department requests."""
        return [
            ("Emergency", "ICU", True),
            ("Emergency", "Surgery", True),
            ("Emergency", "Radiology", True),
            ("Emergency", "General Ward", False),
            ("Emergency", "Pharmacy", False),
            ("ICU", "Emergency", False)
        ]

    def _get_distributed_scenario(self):
        """Scenario with evenly distributed requests across departments."""
        return [
            ("Reception", "Radiology", False),
            ("Radiology", "Laboratory", False),
            ("Laboratory", "Pharmacy", False),
            ("Pharmacy", "ICU", False),
            ("ICU", "Emergency", True),
            ("Emergency", "Surgery", True),
            ("Surgery", "Cardiology", False),
            ("Cardiology", "Neurology", False),
            ("Neurology", "Orthopedics", False),
            ("Orthopedics", "Pediatrics", False),
            ("Pediatrics", "General Ward", False),
            ("General Ward", "ICU", True),
            ("Admin Office", "Reception", False),
            ("Cafeteria", "Admin Office", False),
            ("Emergency", "Cafeteria", False)
        ]

    def _get_complex_benchmark(self):
        """Complex benchmark scenario with 25 transport requests."""
        return [
            # Emergency department requests (some urgent)
            ("Emergency", "ICU", True),
            ("Emergency", "Surgery", True),
            ("Emergency", "Radiology", True),
            ("Emergency", "General Ward", False),
            ("Emergency", "Pharmacy", False),

            # ICU requests
            ("ICU", "Surgery", True),
            ("ICU", "Radiology", False),
            ("ICU", "Pharmacy", False),

            # Surgery department requests
            ("Surgery", "ICU", True),
            ("Surgery", "Recovery", False),
            ("Surgery", "General Ward", False),

            # Radiology requests
            ("Radiology", "Emergency", True),
            ("Radiology", "Oncology", False),
            ("Radiology", "Neurology", False),

            # Other specialized departments
            ("Cardiology", "ICU", True),
            ("Neurology", "Surgery", False),
            ("Orthopedics", "Radiology", False),
            ("Pediatrics", "Emergency", True),
            ("Oncology", "Radiology", False),

            # Support services
            ("Laboratory", "Emergency", True),
            ("Pharmacy", "General Ward", False),
            ("General Ward", "Radiology", False),
            ("Reception", "Cardiology", False),
            ("Cafeteria", "Admin Office", False),
            ("Admin Office", "Reception", False)
        ]

    def run_ilp_benchmark(self, num_transporters, requests, ilp_mode=ILPMode.MAKESPAN, extra_params=None):
        """
        Run a single ILP benchmark with the given configuration.

        Args:
            num_transporters (int): Number of transporters to use
            requests (list): List of transport requests as (origin, destination, urgent) tuples
            ilp_mode (ILPMode): The ILP optimization mode to use
            extra_params (dict): Additional parameters for specific modes (e.g., num_clusters)

        Returns:
            dict: Results including makespan and workload distribution
        """
        # Reset the system state
        self._reset_system_state()

        # Create transporters
        transporters = []
        for i in range(num_transporters):
            name = f"Benchmark_T{i + 1}"
            self.system.add_transporter(name)
            transporters.append(self.system.transport_manager.get_transporter(name))

        # Create transport requests
        for origin, destination, urgent in requests:
            self.system.create_transport_request(origin, destination, "stretcher", urgent)

        # Create optimizer strategy with appropriate parameters
        if extra_params is None:
            extra_params = {}

        strategy = ILPOptimizerStrategy(ilp_mode, **extra_params)

        # Run optimization
        graph = self.system.hospital.get_graph()
        plan = strategy.generate_assignment_plan(transporters, TransportationRequest.pending_requests, graph)

        # Calculate makespan and workload
        makespan = 0
        workload = {}

        for t in transporters:
            assigned_requests = plan.get(t.name, [])
            total_time = self._estimate_execution_time(t, assigned_requests)
            workload[t.name] = total_time
            makespan = max(makespan, total_time)

        return {
            "makespan": makespan,
            "workload": workload,
            "plan": plan
        }

    def run_genetic_benchmark(self, num_transporters, requests, params=None):
        """
        Run a benchmark using the Genetic Algorithm optimizer.

        Args:
            num_transporters (int): Number of transporters to use
            requests (list): List of transport requests
            params (dict): Additional parameters for the genetic algorithm

        Returns:
            dict: Results including makespan and workload
        """
        # Reset the system state
        self._reset_system_state()

        # Create transporters
        transporters = []
        for i in range(num_transporters):
            name = f"Benchmark_T{i + 1}"
            self.system.add_transporter(name)
            transporters.append(self.system.transport_manager.get_transporter(name))

        # Create transport requests
        for origin, destination, urgent in requests:
            self.system.create_transport_request(origin, destination, "stretcher", urgent)

        # Create genetic algorithm strategy
        strategy_params = {}
        if params:
            strategy_params.update(params)

        strategy = GeneticAlgorithmStrategy(**strategy_params)

        # Run optimization
        graph = self.system.hospital.get_graph()
        plan = strategy.generate_assignment_plan(transporters, TransportationRequest.pending_requests, graph)

        # Calculate makespan and workload
        makespan = 0
        workload = {}

        for t in transporters:
            assigned_requests = plan.get(t.name, [])
            total_time = self._estimate_execution_time(t, assigned_requests)
            workload[t.name] = total_time
            makespan = max(makespan, total_time)

        return {
            "makespan": makespan,
            "workload": workload,
            "plan": plan
        }

    def run_random_benchmark(self, num_transporters, requests, runs=1):
        """
        Run random assignment benchmarks.

        Args:
            num_transporters (int): Number of transporters to use
            requests (list): List of transport requests
            runs (int): Number of runs to perform

        Returns:
            list: List of result dictionaries with makespan and workload
        """
        results = []

        for run in range(runs):
            # Reset the system state
            self._reset_system_state()

            # Create transporters
            transporters = []
            for i in range(num_transporters):
                name = f"Benchmark_T{i + 1}"
                self.system.add_transporter(name)
                transporters.append(self.system.transport_manager.get_transporter(name))

            # Create transport requests
            for origin, destination, urgent in requests:
                self.system.create_transport_request(origin, destination, "stretcher", urgent)

            # Create random strategy
            strategy = RandomAssignmentStrategy()

            # Run random assignment
            graph = self.system.hospital.get_graph()
            plan = strategy.generate_assignment_plan(transporters, TransportationRequest.pending_requests, graph)

            # Calculate makespan and workload for this run
            makespan = 0
            workload = {}

            for t in transporters:
                assigned_requests = plan.get(t.name, [])
                total_time = self._estimate_execution_time(t, assigned_requests)
                workload[t.name] = total_time
                makespan = max(makespan, total_time)

            # Store result for this run
            results.append({
                "makespan": makespan,
                "workload": workload if run == 0 else None,  # Only store workload for first run to save memory
                "plan": plan if run == 0 else None
            })

        return results

    def _estimate_execution_time(self, transporter, requests):
        """
        Estimate the time a transporter would take to complete all assigned requests.

        Args:
            transporter: The transporter object
            requests: List of request objects

        Returns:
            float: Estimated completion time in seconds
        """
        time = 0
        current_location = transporter.current_location
        graph = self.system.hospital.get_graph()

        for request in requests:
            # Travel to request origin
            path_to_origin, _ = transporter.pathfinder.dijkstra(current_location, request.origin)
            to_origin_time = sum(
                graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
                for i in range(len(path_to_origin) - 1)
            )

            # Travel to request destination
            path_to_dest, _ = transporter.pathfinder.dijkstra(request.origin, request.destination)
            to_dest_time = sum(
                graph.get_edge_weight(path_to_dest[i], path_to_dest[i + 1])
                for i in range(len(path_to_dest) - 1)
            )

            time += to_origin_time + to_dest_time
            current_location = request.destination

        return time

    def _reset_system_state(self):
        """Reset the system state for a new benchmark run."""
        # Clear transporters
        self.system.transport_manager.transporters.clear()

        # Clear all request lists
        TransportationRequest.pending_requests.clear()
        TransportationRequest.ongoing_requests.clear()
        TransportationRequest.completed_requests.clear()

    def calculate_statistics(self, times):
        """
        Calculate statistics for a list of completion times.

        Args:
            times (list): List of completion times

        Returns:
            dict: Dictionary of statistics
        """
        if not times:
            return {
                "mean": 0,
                "median": 0,
                "std": 0,
                "min": 0,
                "max": 0
            }

        return {
            "mean": np.mean(times),
            "median": np.median(times),
            "std": np.std(times),
            "min": np.min(times),
            "max": np.max(times)
        }

    def calculate_workload_statistics(self, workload):
        """
        Calculate workload distribution statistics.

        Args:
            workload (dict): Dictionary mapping transporter names to times

        Returns:
            dict: Dictionary of statistics
        """
        if not workload:
            return {
                "std": 0,
                "mean": 0,
                "min": 0,
                "max": 0
            }

        values = list(workload.values())
        return {
            "std": np.std(values),
            "mean": np.mean(values),
            "min": np.min(values),
            "max": np.max(values)
        }

