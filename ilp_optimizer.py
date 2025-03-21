from pulp import LpMinimize, LpProblem, LpVariable, lpSum
import itertools


class ILPOptimizer:
    def __init__(self, transporters, transport_requests, graph):
        self.transporters = transporters
        self.transport_requests = transport_requests
        self.graph = graph

    def estimate_travel_time(self, transporter, request_obj):
        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request_obj.origin)
        time_to_origin = sum(self.graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
                             for i in range(len(path_to_origin) - 1))

        path_to_destination, _ = transporter.pathfinder.dijkstra(request_obj.origin, request_obj.destination)
        time_to_destination = sum(self.graph.get_edge_weight(path_to_destination[i], path_to_destination[i + 1])
                                  for i in range(len(path_to_destination) - 1))

        return time_to_origin + time_to_destination

    def get_assign_vars(self):
        """Creates binary decision variables for all possible (t, r) assignments."""
        assign_vars = {}
        for t, r in itertools.product(self.transporters, self.transport_requests):
            assign_vars[(t.name, r.origin, r.destination)] = LpVariable(
                f"assign_{t.name}_{r.origin}_{r.destination}", cat="Binary"
            )
        return assign_vars

    def add_objective_function(self, prob, assign_vars):
        """Objective: minimize total travel time across all assignments."""
        prob += lpSum(
            assign_vars[(t.name, r.origin, r.destination)] * self.estimate_travel_time(t, r)
            for t in self.transporters for r in self.transport_requests
        )

    def add_constraints(self, prob, assign_vars):
        # 🚫 Each request must be assigned to exactly one transporter
        for r in self.transport_requests:
            prob += lpSum(assign_vars[(t.name, r.origin, r.destination)] for t in self.transporters) == 1

        # ✅ Allow multiple requests per transporter (queued), so no limit here

    def extract_solution(self, assign_vars):
        """
        Groups assignments by transporter and orders them by estimated travel time.
        """
        transporter_assignments = {}

        for (t_name, origin, destination), var in assign_vars.items():
            if var.value() == 1:
                if t_name not in transporter_assignments:
                    transporter_assignments[t_name] = []
                transporter_assignments[t_name].append((origin, destination))

        # Optional: sort each transporter’s jobs by estimated travel time
        for t_name, assignments in transporter_assignments.items():
            transporter = next(t for t in self.transporters if t.name == t_name)
            assignments.sort(key=lambda pair: self.estimate_travel_time(
                transporter,
                next(r for r in self.transport_requests if r.origin == pair[0] and r.destination == pair[1])
            ))

        return transporter_assignments

    def optimize_transport_schedule(self):
        if not self.transport_requests or not self.transporters:
            print("❌ No transporters or requests available for optimization!")
            return None

        print("🔍 Running ILP Optimization with queueing support...")

        prob = LpProblem("Transport_Optimization", LpMinimize)
        assign_vars = self.get_assign_vars()
        self.add_objective_function(prob, assign_vars)
        self.add_constraints(prob, assign_vars)
        prob.solve()

        assignments = self.extract_solution(assign_vars)

        print("✅ Optimized transport assignments with queuing:")
        for t, tasks in assignments.items():
            print(f"  🚑 {t}: {tasks}")

        return assignments
