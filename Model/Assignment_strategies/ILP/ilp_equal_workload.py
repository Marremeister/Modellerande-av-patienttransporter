from Model.Assignment_strategies.ILP.ilp_core import ILPCore
from pulp import lpSum

class ILPEqualWorkload(ILPCore):
    def define_objective(self):
        total_work = {
            t.name: lpSum(
                self.variables[(t.name, r)] * self.estimate_travel_time(t, r)
                for r in self.requests
            )
            for t in self.transporters
        }

        mean_work = lpSum(total_work.values()) / len(self.transporters)
        self.model += lpSum((total_work[t] - mean_work) ** 2 for t in total_work)
