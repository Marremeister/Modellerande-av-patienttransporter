import random
from assignment_strategy import AssignmentStrategy
from random_assignment import RandomAssignment

#Värt att skapa en konstruktor, designen känns klunkig.

class RandomAssignmentStrategy(AssignmentStrategy):
    def generate_assignment_plan(self, transporters, requests, graph):
        randomizer = RandomAssignment(transporters, requests, graph)
        return randomizer.generate_assignment_plan(transporters, requests) #Varför inte använda variable från konstruktor?

    def estimate_travel_time(self, transporter, request):
        randomizer = RandomAssignment([], [], transporter.hospital.get_graph())
        return randomizer.estimate_travel_time(transporter, request)