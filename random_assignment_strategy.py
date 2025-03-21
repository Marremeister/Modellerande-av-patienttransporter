import random
from assignment_strategy import AssignmentStrategy

class RandomAssignmentStrategy(AssignmentStrategy):
    def generate_assignment_plan(self, transporters, requests, graph):
        plan = {t.name: [] for t in transporters}
        available = list(transporters)

        for request in requests:
            if not available:
                available = list(transporters)
            transporter = random.choice(available)
            plan[transporter.name].append(request)

        return plan

    def estimate_travel_time(self, transporter, request):
        # Just approximate with 1 for now (or a small constant)
        return 1
