from abc import ABC, abstractmethod
import pulp


class ILPCore(ABC):
    def __init__(self, transporters, requests, graph):
        self.transporters = transporters
        self.requests = requests
        self.graph = graph
        self.model = pulp.LpProblem("Transport_Assignment", pulp.LpMinimize)
        self.assign_vars = {}

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

    def add_constraints(self):
        # Each request must be assigned to exactly one transporter
        for r in self.requests:
            self.model += (
                pulp.lpSum(self.assign_vars[(t.name, r.id)] for t in self.transporters) == 1,
                f"UniqueAssignment_{r.id}"
            )

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

        # Sort assignments per transporter by travel time from current location
        for t in self.transporters:
            plan[t.name] = self.sort_requests_by_greedy_chain(t, plan[t.name])

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

    def sort_requests_by_greedy_chain(self, transporter, requests):
        from copy import deepcopy
        remaining = deepcopy(requests)
        ordered = []
        current_location = transporter.current_location

        while remaining:
            # Find the request whose origin is closest to current_location
            next_request = min(
                remaining,
                key=lambda r: self.estimate_point_to_point_time(current_location, r.origin)
            )
            ordered.append(next_request)
            current_location = next_request.destination
            remaining.remove(next_request)

        return ordered

    def estimate_point_to_point_time(self, start, end):
        path, _ = self.transporters[0].pathfinder.dijkstra(start, end)
        return sum(self.graph.get_edge_weight(path[i], path[i + 1]) for i in range(len(path) - 1))
