from assignment_strategy import AssignmentStrategy
from ilp_optimizer import ILPOptimizer

class ILPOptimizerStrategy(AssignmentStrategy):
    def generate_assignment_plan(self, transporters, requests, graph):
        optimizer = ILPOptimizer(transporters, requests, graph)
        return optimizer.generate_assignment_plan()

    def estimate_travel_time(self, transporter, request):
        # Fallback ILP instance to reuse estimation logic
        return ILPOptimizer([], [], transporter.hospital.get_graph()).estimate_travel_time(transporter, request)
