import random
from assignment_strategy import AssignmentStrategy
from random_assignment_manager import RandomAssignmentManager

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
        return RandomAssignmentManager.estimate_travel_time(transporter, request)
