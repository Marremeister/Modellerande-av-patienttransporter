from abc import ABC, abstractmethod
import pulp


class ILPCore(ABC):
    def __init__(self, transporters, requests, graph):
        self.transporters = transporters
        self.requests = requests
        self.graph = graph
        self.model = pulp.LpProblem("Transport_Assignment", pulp.LpMinimize)
        self.assign_vars = {}
        self.order_vars = {}

    def build_and_solve(self):
        self.define_variables()
        self.add_constraints()
        self.define_objective()

        self.model.solve(pulp.PULP_CBC_CMD(msg=False))
        return self.extract_assignments()

    def define_variables(self):
        for t in self.transporters:
            for r in self.requests:
                var_name = f"x_{t.name}_{r.id}"
                self.assign_vars[(t.name, r.id)] = pulp.LpVariable(var_name, cat="Binary")

            for i, r1 in enumerate(self.requests):
                for j, r2 in enumerate(self.requests):
                    if i == j:
                        continue
                    order_name = f"order_{t.name}_{r1.id}_{r2.id}"
                    self.order_vars[(t.name, r1.id, r2.id)] = pulp.LpVariable(order_name, cat="Binary")

    def add_constraints(self):
        # Each request must be assigned to exactly one transporter
        for r in self.requests:
            self.model += (
                pulp.lpSum(self.assign_vars[(t.name, r.id)] for t in self.transporters) == 1,
                f"UniqueAssignment_{r.id}"
            )

        for t in self.transporters:
            for r1 in self.requests:
                for r2 in self.requests:
                    if r1 == r2:
                        continue

                    order = self.order_vars[(t.name, r1.id, r2.id)]
                    reverse_order = self.order_vars[(t.name, r2.id, r1.id)]
                    x1 = self.assign_vars[(t.name, r1.id)]
                    x2 = self.assign_vars[(t.name, r2.id)]

                    # Prevent cycles
                    self.model += (
                        order + reverse_order <= 1,
                        f"NoCycle_{t.name}_{r1.id}_{r2.id}"
                    )

                    # Only enforce ordering if both are assigned to same transporter
                    self.model += (order <= x1, f"OrderIfAssigned1_{t.name}_{r1.id}_{r2.id}")
                    self.model += (order <= x2, f"OrderIfAssigned2_{t.name}_{r1.id}_{r2.id}")

    @abstractmethod
    def define_objective(self):
        """Implemented by subclasses: defines the optimization objective."""
        pass

    def extract_assignments(self):
        plan = {t.name: [] for t in self.transporters}

        for (t_name, r_id), var in self.assign_vars.items():
            if var.varValue == 1:
                req = next(r for r in self.requests if r.id == r_id)
                plan[t_name].append(req)

        for t in self.transporters:
            assigned = plan[t.name]
            sorted_requests = []
            while assigned:
                for candidate in assigned:
                    # No request should come before this one
                    if all(
                        self.order_vars.get((t.name, other.id, candidate.id), None) is None or
                        self.order_vars[(t.name, other.id, candidate.id)].varValue != 1
                        for other in assigned if other != candidate
                    ):
                        sorted_requests.append(candidate)
                        assigned.remove(candidate)
                        break
            plan[t.name] = sorted_requests

        return plan

    def estimate_travel_time(self, transporter, request):
        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request.origin)
        to_origin_time = sum(
            self.graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
            for i in range(len(path_to_origin) - 1)
        )

        path_to_dest, _ = transporter.pathfinder.dijkstra(request.origin, request.destination)
        to_dest_time = sum(
            self.graph.get_edge_weight(path_to_dest[i], path_to_dest[i + 1])
            for i in range(len(path_to_dest) - 1)
        )

        return to_origin_time + to_dest_time
