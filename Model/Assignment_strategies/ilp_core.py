from abc import ABC, abstractmethod
import pulp


class ILPCore(ABC):
    def __init__(self, transporters, requests, graph):
        self.transporters = transporters
        self.requests = requests
        self.graph = graph
        self.model = pulp.LpProblem("Transport_Assignment", pulp.LpMinimize)
        self.variables = {}

    def build_and_solve(self):
        self.define_variables()
        self.add_constraints()
        self.define_objective()

        self.model.solve(pulp.PULP_CBC_CMD(msg=False))
        return self.extract_assignments()

    def define_variables(self):
        for t in self.transporters:
            for r in self.requests:
                var_name = f"x_{t.name}_{r.origin}_{r.destination}"
                self.variables[(t.name, r)] = pulp.LpVariable(var_name, cat="Binary")

    def add_constraints(self):
        # Every request is assigned to exactly one transporter
        for r in self.requests:
            self.model += (
                pulp.lpSum(self.variables[(t.name, r)] for t in self.transporters) == 1,
                f"Request_{r.origin}_{r.destination}_assigned"
            )

        # Transporter cannot handle more than one request at a time (optional if needed)
        # Add more constraints here as needed

    @abstractmethod
    def define_objective(self):
        """Implemented by subclasses: defines the optimization objective."""
        pass

    def extract_assignments(self):
        plan = {t.name: [] for t in self.transporters}
        for (t_name, r), var in self.variables.items():
            if var.varValue == 1:
                plan[t_name].append(r)
        return plan

    def estimate_travel_time(self, transporter, request):
        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request.origin)
        time_to_origin = sum(self.graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
                             for i in range(len(path_to_origin) - 1))

        path_to_dest, _ = transporter.pathfinder.dijkstra(request.origin, request.destination)
        time_to_dest = sum(self.graph.get_edge_weight(path_to_dest[i], path_to_dest[i + 1])
                           for i in range(len(path_to_dest) - 1))

        return time_to_origin + time_to_dest

