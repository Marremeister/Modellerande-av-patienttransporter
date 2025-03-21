import random
import eventlet
from assignment_strategy import AssignmentStrategy

class RandomAssignmentManager(AssignmentStrategy):
    def __init__(self, transport_manager, hospital, socketio):
        self.tm = transport_manager
        self.hospital = hospital
        self.socketio = socketio

    def assign_requests(self):
        self.socketio.emit("transport_log", {
            "message": "🎲 Random assignment triggered..."
        })

        available = [t for t in self.tm.transporters if not t.is_busy and t.status == "active"]
        pending = list(self.tm.pending_requests)
        random.shuffle(pending)

        for request in pending:
            if not available:
                break

            transporter = available.pop()
            self.tm.pending_requests.remove(request)
            self.tm.ongoing_requests.append(request)
            request.status = "ongoing"
            transporter.current_task = request
            transporter.is_busy = True

            self.socketio.emit("transport_log", {
                "message": f"🎲 {transporter.name} randomly assigned: {request.origin} ➝ {request.destination}"
            })

            eventlet.spawn_n(self.tm.process_transport, transporter, request)
