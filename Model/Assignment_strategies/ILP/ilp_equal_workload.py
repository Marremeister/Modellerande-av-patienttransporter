from pulp import lpSum, LpVariable
from Model.Assignment_strategies.ILP.ilp_core import ILPCore


class ILPEqualWorkload(ILPCore):
    def define_objective(self):
        self.max_requests = LpVariable("max_requests", lowBound=0)

        for t in self.transporters:
            total = lpSum(
                self.assign_vars[(t.name, r.id)] for r in self.requests
            )
            self.model += (total <= self.max_requests, f"MaxRequests_{t.name}")

        self.model += self.max_requests
