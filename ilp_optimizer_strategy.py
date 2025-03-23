# ilp_optimizer_strategy.py
from assignment_strategy import AssignmentStrategy
from ilp_mode import ILPMode

# Import your ILPCore subclasses
from ilp_makespan import ILPMakespan
from ilp_equal_workload import ILPEqualWorkload
from ilp_urgency_first import ILPUrgencyFirst


class ILPOptimizerStrategy(AssignmentStrategy):
    def __init__(self, mode: ILPMode = ILPMode.MAKESPAN):
        self.mode = mode

    def generate_assignment_plan(self, transporters, requests, graph):
        return self._get_ilp_core(transporters, requests, graph).build_and_solve()

    def estimate_travel_time(self, transporter, request):
        return transporter.pathfinder.estimate_cost(transporter.current_location, request.origin) + \
               transporter.pathfinder.estimate_cost(request.origin, request.destination)

    def get_optimizer(self, transporters, requests, graph):
        return self._get_ilp_core(transporters, requests, graph)

    def _get_ilp_core(self, transporters, requests, graph):
        if self.mode == ILPMode.EQUAL_WORKLOAD:
            return ILPEqualWorkload(transporters, requests, graph)
        elif self.mode == ILPMode.URGENCY_FIRST:
            return ILPUrgencyFirst(transporters, requests, graph)
        else:
            return ILPMakespan(transporters, requests, graph)
