from pulp import lpSum
from Model.Assignment_strategies.ILP.ilp_core import ILPCore


class ILPUrgencyFirst(ILPCore):
    def define_objective(self):
        self.model += lpSum(
            self.assign_vars[(t.name, r.id)] * (10 if r.urgent else 1)
            for t in self.transporters
            for r in self.requests
        )
