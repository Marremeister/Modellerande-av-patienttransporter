from pulp import LpMinimize, LpProblem, LpVariable, lpSum
import itertools

class ILPOptimizer:
    def __init__(self, transporters, transport_requests, graph):
        """
        Initialize the ILP Optimizer with transporters, requests, and hospital graph.
        """
        self.transporters = transporters
        self.transport_requests = transport_requests
        self.graph = graph  # 🔹 Store the hospital's graph model

    def estimate_travel_time(self, transporter, request_obj):
        """
        Estimates the travel time for a transporter to complete a transport request.
        Travel time is calculated based on the graph edge weights.
        """
        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request_obj.origin)
        time_to_origin = sum(self.graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
                             for i in range(len(path_to_origin) - 1))

        path_to_destination, _ = transporter.pathfinder.dijkstra(request_obj.origin, request_obj.destination)
        time_to_destination = sum(self.graph.get_edge_weight(path_to_destination[i], path_to_destination[i + 1])
                                  for i in range(len(path_to_destination) - 1))

        return time_to_origin + time_to_destination

    def get_assign_vars(self):
        """Creates decision variables for transport assignment."""
        assign_vars = {}
        for t, r in itertools.product(self.transporters, self.transport_requests):
            assign_vars[(t.name, r.origin, r.destination)] = LpVariable(
                f"assign_{t.name}_{r.origin}_{r.destination}", cat="Binary"
            )
        return assign_vars

    def add_objective_function(self, prob, assign_vars):
        """Adds the objective function to minimize total transport time."""
        prob += lpSum(
            assign_vars[(t.name, r.origin, r.destination)] * self.estimate_travel_time(t, r)
            for t, r in itertools.product(self.transporters, self.transport_requests)
        )

    def add_constraints(self, prob, assign_vars):
        """Adds constraints to ensure valid transporter assignments."""
        # Constraint: Each request must be assigned to exactly one transporter
        for r in self.transport_requests:
            prob += lpSum(assign_vars[(t.name, r.origin, r.destination)] for t in self.transporters) == 1

        # Constraint: Each transporter can only handle one transport at a time
        for t in self.transporters:
            prob += lpSum(assign_vars[(t.name, r.origin, r.destination)] for r in self.transport_requests) <= 1

    def extract_solution(self, assign_vars):
        """Extracts the optimal transporter-request assignments."""
        optimized_assignments = [
            (t_name, origin, destination)
            for (t_name, origin, destination), var in assign_vars.items() if var.value() == 1
        ]
        return optimized_assignments

    def optimize_transport_schedule(self):
        """
        Uses Integer Linear Programming (ILP) to assign transport requests to transporters optimally.
        """
        if not self.transport_requests or not self.transporters:
            print("❌ No transporters or requests available for optimization!")
            return None

        print("🔍 Running ILP Optimization for transport assignments...")

        # Define the ILP problem
        prob = LpProblem("Transport_Optimization", LpMinimize)

        # Step 1: Get decision variables
        assign_vars = self.get_assign_vars()

        # Step 2: Add objective function
        self.add_objective_function(prob, assign_vars)

        # Step 3: Add constraints
        self.add_constraints(prob, assign_vars)

        # Solve the ILP problem
        prob.solve()

        # Step 4: Extract the solution
        optimized_assignments = self.extract_solution(assign_vars)

        print("✅ Optimal Transport Assignments:", optimized_assignments)
        return optimized_assignments
