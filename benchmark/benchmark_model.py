# benchmark_model.py

from Model.model_transportation_request import TransportationRequest
import numpy as np

class BenchmarkModel:
    def __init__(self, system):
        self.system = system
        self.results = {}

    def run_benchmark(self, strategy_type, runs, transporter_names, requests):
        durations = []

        for _ in range(runs):
            self._reset_system()
            self._add_transporters(transporter_names)

            for origin, dest in requests:
                self.system.create_transport_request(origin, dest)

            if strategy_type == "random":
                self.system.enable_random_mode()
            else:
                self.system.enable_optimized_mode()

            transporters = self.system.transport_manager.get_transporter_objects()
            pending = TransportationRequest.pending_requests
            graph = self.system.hospital.get_graph()
            strategy = self.system.transport_manager.assignment_strategy
            plan = strategy.generate_assignment_plan(transporters, pending, graph)

            if not plan:
                durations.append(float("inf"))
                continue

            max_duration = 0
            for transporter in transporters:
                assigned_requests = plan.get(transporter.name, [])
                t_time = self.simulate_execution_time(transporter, assigned_requests, graph)
                max_duration = max(max_duration, t_time)

            durations.append(max_duration)

        return durations

    # benchmark_model.py (inside BenchmarkModel)
    def generate_assignment_plan(self, strategy_type, transporter_names, requests):
        self._reset_system()
        self._add_transporters(transporter_names)

        for origin, dest in requests:
            self.system.create_transport_request(origin, dest)

        if strategy_type == "random":
            self.system.enable_random_mode()
        else:
            self.system.enable_optimized_mode()

        transporters = self.system.transport_manager.get_transporter_objects()
        pending = TransportationRequest.pending_requests
        graph = self.system.hospital.get_graph()
        strategy = self.system.transport_manager.assignment_strategy

        return strategy.generate_assignment_plan(transporters, pending, graph), transporters

    def get_workload_distribution(self, strategy_type, transporter_names, requests):
        plan, transporters = self.generate_assignment_plan(strategy_type, transporter_names, requests)
        strategy = self.system.transport_manager.assignment_strategy

        return {
            t.name: sum(strategy.estimate_travel_time(t, req) for req in plan.get(t.name, []))
            for t in transporters
        }

    def simulate_execution_time(self, transporter, requests, graph):
        time = 0
        current_location = transporter.current_location

        for request in requests:
            # Travel to request origin
            path_to_origin, _ = transporter.pathfinder.dijkstra(current_location, request.origin)
            to_origin_time = sum(
                graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
                for i in range(len(path_to_origin) - 1)
            )

            # Perform transport
            path_to_dest, _ = transporter.pathfinder.dijkstra(request.origin, request.destination)
            to_dest_time = sum(
                graph.get_edge_weight(path_to_dest[i], path_to_dest[i + 1])
                for i in range(len(path_to_dest) - 1)
            )

            time += to_origin_time + to_dest_time
            current_location = request.destination

        return time

    def calculate_workload_std(self, workload_dict):
        return np.std(list(workload_dict.values()))

    def _reset_system(self):
        self.system.transport_manager.transporters = []
        TransportationRequest.pending_requests.clear()
        TransportationRequest.ongoing_requests.clear()
        TransportationRequest.completed_requests.clear()

    def _add_transporters(self, names):
        for name in names:
            self.system.add_transporter(name)
