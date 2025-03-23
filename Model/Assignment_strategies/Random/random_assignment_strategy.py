from Model.Assignment_strategies.assignment_strategy import AssignmentStrategy
from Model.Assignment_strategies.Random.random_assignment import RandomAssignment

class RandomAssignmentStrategy(AssignmentStrategy):
    def generate_assignment_plan(self, transporters, assignable_requests, graph):
        randomizer = RandomAssignment(transporters, assignable_requests, graph)
        return randomizer.generate_assignment_plan(transporters, assignable_requests)

    def estimate_travel_time(self, transporter, request):
        randomizer = RandomAssignment([], [], transporter.hospital.get_graph())
        return randomizer.estimate_travel_time(transporter, request)

    def get_optimizer(self, transporters, assignable_requests, graph):
        return RandomAssignment(transporters, assignable_requests, graph)
