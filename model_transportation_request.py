from datetime import datetime

class TransportationRequest:
    def __init__(self, request_time=None, urgent=False, transport_type="", origin="", destination=""):
        """Initializes a transportation request with details about the transport."""
        self.request_time = request_time if request_time else datetime.now()
        self.urgent = urgent  # True for urgent, False for non-urgent
        self.transport_type = transport_type  # "stretcher", "wheelchair", "samples"
        self.origin = origin  # Starting department
        self.destination = destination  # Target department (e.g., "Surgery", "X-ray")

    def __str__(self):
        """Returns a formatted string representation of the request."""
        urgency_status = "Urgent" if self.urgent else "Non-Urgent"
        return (f"Request Time: {self.request_time}, Urgency: {urgency_status}, "
                f"Type: {self.transport_type}, Origin: {self.origin}, Destination: {self.destination}")
