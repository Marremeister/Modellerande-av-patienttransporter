from datetime import datetime

class TransportationRequest:
    def __init__(self, request_time, origin, destination, transport_type="stretcher", urgent=False):
        """Creates a transport request."""
        self.request_time = request_time
        self.origin = origin
        self.destination = destination
        self.transport_type = transport_type
        self.urgent = urgent
        self.status = "pending"  # New status: pending, ongoing, completed

    def mark_as_ongoing(self):
        """Marks the request as ongoing."""
        self.status = "ongoing"

    def mark_as_completed(self):
        """Marks the request as completed."""
        self.status = "completed"

    def to_dict(self):
        """Returns the request as a dictionary for JSON serialization."""
        return {
            "origin": self.origin,
            "destination": self.destination,
            "transport_type": self.transport_type,
            "urgent": self.urgent,
            "status": self.status
        }

    def __str__(self):
        """Returns a formatted string representation of the request."""
        urgency_status = "Urgent" if self.urgent else "Non-Urgent"
        return (f"Request Time: {self.request_time}, Urgency: {urgency_status}, "
                f"Type: {self.transport_type}, Origin: {self.origin}, Destination: {self.destination}")
