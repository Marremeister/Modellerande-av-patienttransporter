class TransportationRequest:
    def __init__(self, origin, destination, transport_type="stretcher", urgent=False):
        """Represents a transport request for a patient/item."""
        self.origin = origin
        self.destination = destination
        self.transport_type = transport_type
        self.urgent = urgent
        self.status = "pending"  # Default status

    def mark_as_ongoing(self):
        """Marks request as ongoing."""
        self.status = "ongoing"

    def mark_as_completed(self):
        """Marks request as completed."""
        self.status = "completed"


    def to_dict(self):
        """Convert request to JSON serializable format"""
        return {
            "request_time": self.request_time,
            "origin": self.origin,
            "destination": self.destination,
            "transport_type": self.transport_type,
            "urgent": self.urgent,
            "status": self.status
        }

    @classmethod
    def create(cls, origin, destination, transport_type="stretcher", urgent=False):
        """Creates and stores a new transport request."""
        request_obj = cls(request_time=None, origin=origin, destination=destination, transport_type=transport_type, urgent=urgent)
        cls.pending_requests.append(request_obj)
        print(f"📦 Transport request created: {origin} → {destination} ({transport_type}, Urgent: {urgent})")
        return request_obj

    @classmethod
    def get_requests(cls):
        """Returns all transport requests grouped by status."""
        return {
            "pending": [r.to_dict() for r in cls.pending_requests],
            "ongoing": [r.to_dict() for r in cls.ongoing_requests],
            "completed": [r.to_dict() for r in cls.completed_requests]
        }
