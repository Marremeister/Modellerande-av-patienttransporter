# ilp_optimizer_strategy.py
from Model.Assignment_strategies.assignment_strategy import AssignmentStrategy
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode

# Import your ILPCore subclasses
from Model.Assignment_strategies.ILP.ilp_makespan import ILPMakespan
from Model.Assignment_strategies.ILP.ilp_equal_workload import ILPEqualWorkload
from Model.Assignment_strategies.ILP.ilp_urgency_first import ILPUrgencyFirst


class ILPOptimizerStrategy(AssignmentStrategy):
    def __init__(self, mode=ILPMode.MAKESPAN):
        self.mode = mode
        self.optimizer = None

    def generate_assignment_plan(self, transporters, requests, graph):
        self.optimizer = self.get_optimizer(transporters, requests, graph)
        return self.optimizer.build_and_solve()

    def get_optimizer(self, transporters, requests, graph):
        if self.mode == ILPMode.MAKESPAN:
            return ILPMakespan(transporters, requests, graph)
        elif self.mode == ILPMode.EQUAL_WORKLOAD:
            return ILPEqualWorkload(transporters, requests, graph)
        elif self.mode == ILPMode.URGENCY_FIRST:
            return ILPUrgencyFirst(transporters, requests, graph)
        else:
            raise ValueError(f"Unsupported ILP Mode: {self.mode}")

    def estimate_travel_time(self, transporter, request):
        if not self.optimizer:
            raise RuntimeError("ILPOptimizerStrategy: optimizer not initialized.")
        return self.optimizer.estimate_travel_time(transporter, request)