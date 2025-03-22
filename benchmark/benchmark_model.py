# benchmark_model.py
from hospital_controller import HospitalController
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
            pending = self.system.transport_manager.pending_requests
            graph = self.system.hospital.get_graph()
            strategy = self.system.transport_manager.assignment_strategy
            plan = strategy.generate_assignment_plan(transporters, pending, graph)

            if not plan:
                durations.append(float("inf"))
                continue

            max_duration = 0
            for transporter in transporters:
                total_time = sum(strategy.estimate_travel_time(transporter, t) for t in plan.get(transporter.name, []))
                max_duration = max(max_duration, total_time)

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
        pending = self.system.transport_manager.pending_requests
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

    def calculate_workload_std(self, workload_dict):
        return np.std(list(workload_dict.values()))

    def _reset_system(self):
        tm = self.system.transport_manager
        tm.transporters = []
        tm.pending_requests = []
        tm.ongoing_requests = []
        tm.completed_requests = []

    def _add_transporters(self, names):
        for name in names:
            self.system.add_transporter(name)
