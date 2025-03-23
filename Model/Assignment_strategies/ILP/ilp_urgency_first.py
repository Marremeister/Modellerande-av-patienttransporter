from Model.Assignment_strategies.ILP.ilp_core import ILPCore
from pulp import lpSum

class ILPUrgencyFirst(ILPCore):
    def define_objective(self):
        self.model += lpSum(
            self.variables[(t.name, r)] * (
                self.estimate_travel_time(t, r) * (0.5 if r.urgent else 1.0)
            )
            for t in self.transporters
            for r in self.requests
        )
