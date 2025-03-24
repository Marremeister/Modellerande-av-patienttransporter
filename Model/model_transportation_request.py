import uuid
import time

class TransportationRequest:
    # Class-level tracking of all requests
    pending_requests = []
    ongoing_requests = []
    completed_requests = []

    def __init__(self, origin, destination, transport_type="stretcher", urgent=False, request_time=None):
        self.id = str(uuid.uuid4())  # Unique ID for each request
        self.origin = origin
        self.destination = destination
        self.transport_type = transport_type
        self.urgent = urgent
        self.status = "pending"
        self.request_time = request_time or time.time()
        self.has_started = False  # ✅ Track if the request has been started
        self.assigned_transporter = None

    def assign_transporter_to_request(self, transporter):
        self.assigned_transporter = transporter

    def get_transporter_name(self):
        return self.assigned_transporter.name if self.assigned_transporter else "-"

    def mark_as_ongoing(self):
        self.status = "ongoing"
        self.has_started = True  # ✅ Mark it as started
        if self in TransportationRequest.pending_requests:
            TransportationRequest.pending_requests.remove(self)
        if self not in TransportationRequest.ongoing_requests:
            TransportationRequest.ongoing_requests.append(self)

    def mark_as_completed(self):
        self.status = "completed"
        if self in TransportationRequest.ongoing_requests:
            TransportationRequest.ongoing_requests.remove(self)
        if self not in TransportationRequest.completed_requests:
            TransportationRequest.completed_requests.append(self)

    def is_reassignable(self):
        return not self.has_started  # ✅ Used for optimization filtering

    def to_dict(self):
        return {
            "id": self.id,
            "request_time": self.request_time,
            "origin": self.origin,
            "destination": self.destination,
            "transport_type": self.transport_type,
            "urgent": self.urgent,
            "status": self.status,
            "has_started": self.has_started  # ✅ Expose to frontend/logs if needed
        }

    @classmethod
    def create(cls, origin, destination, transport_type="stretcher", urgent=False):
        request_obj = cls(origin=origin, destination=destination, transport_type=transport_type, urgent=urgent)
        cls.pending_requests.append(request_obj)
        print(f"📦 Transport request created: {origin} → {destination} ({transport_type}, Urgent: {urgent})")
        return request_obj

    @classmethod
    def get_requests(cls):
        return {
            "pending": [r.to_dict() for r in cls.pending_requests],
            "ongoing": [r.to_dict() for r in cls.ongoing_requests],
            "completed": [r.to_dict() for r in cls.completed_requests]
        }

    @classmethod
    def remove_completed_request(cls, request_key):
        cls.completed_requests = [
            r for r in cls.completed_requests
            if f"{r.origin}-{r.destination}" != request_key
        ]

    @classmethod
    def remove_from_tracking(cls, request):
        if request in cls.pending_requests:
            cls.pending_requests.remove(request)
        if request in cls.ongoing_requests:
            cls.ongoing_requests.remove(request)
        if request in cls.completed_requests:
            cls.completed_requests.remove(request)

    @classmethod
    def get_assignable_requests(cls):
        return [r for r in cls.pending_requests if not hasattr(r, 'locked') or not r.locked]

    def __repr__(self):
        return f"<Request {self.id[:6]}: {self.origin} → {self.destination}, urgent={self.urgent}>"

    def __eq__(self, other):
        return isinstance(other, TransportationRequest) and self.id == other.id

    def __hash__(self):
        return hash(self.id)
