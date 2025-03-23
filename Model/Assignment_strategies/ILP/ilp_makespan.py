from Model.Assignment_strategies.ILP.ilp_core import ILPCore
from pulp import LpVariable, lpSum

class ILPMakespan(ILPCore):
    def define_objective(self):
        self.makespan = LpVariable("makespan", lowBound=0)

        for t in self.transporters:
            total_time = lpSum(
                self.variables[(t.name, r)] * self.estimate_travel_time(t, r)
                for r in self.requests
            )
            self.model += total_time <= self.makespan

        self.model += self.makespan
