from abc import ABC, abstractmethod

class AssignmentStrategy(ABC):
    @abstractmethod
    def generate_assignment_plan(self, transporters, requests, graph):
        """Return a dictionary {transporter_name: [list_of_requests]}"""
        pass

    @abstractmethod
    def estimate_travel_time(self, transporter, request):
        """Return estimated time from transporter to complete a request"""
        pass

    def get_optimizer(self, transporters, requests, graph):
        return None  # Default: no optimizer
