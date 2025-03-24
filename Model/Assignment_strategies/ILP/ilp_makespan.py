from pulp import lpSum, LpVariable
from Model.Assignment_strategies.ILP.ilp_core import ILPCore


class ILPMakespan(ILPCore):
    def define_objective(self):
        self.makespan = LpVariable("makespan", lowBound=0)

        for t in self.transporters:
            total_time = lpSum(
                self.assign_vars[(t.name, r.id)] * self.estimate_travel_time(t, r)
                for r in self.requests
            )
            self.model += (total_time <= self.makespan, f"MakespanLimit_{t.name}")

        self.model += self.makespan

