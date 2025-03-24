import eventlet
from Model.model_transportation_request import TransportationRequest

class TransportAssignmentHandler:
    def __init__(self, socketio, transport_manager):
        self.socketio = socketio
        self.tm = transport_manager

    def assign(self, transporter, request):
        if transporter.status == "inactive":
            self._log(f"❌ {transporter.name} is inactive. Cannot assign transport.")
            return

        request.assign_transporter_to_request(transporter)
        request.mark_as_ongoing()

        self._emit_assignment_log(transporter, request)

        if transporter.is_busy:
            transporter.task_queue.append(request)
            self._log(f"🕒 {transporter.name} is busy. Queued {request.origin} → {request.destination}")
        else:
            transporter.current_task = request
            transporter.is_busy = True
            eventlet.spawn_n(self.tm.process_transport, transporter, request)

    def _emit_assignment_log(self, transporter, request):
        msg = f"🚑 {transporter.name} assigned: {request.origin} ➝ {request.destination} ({request.transport_type})"
        self.socketio.emit("transport_log", {"message": msg})

        # Emit to frontend dropdown refresh
        self.socketio.emit("transport_status_update", {
            "status": "ongoing",
            "request": {
                "origin": request.origin,
                "destination": request.destination,
                "transport_type": request.transport_type
            }
        })

    def _log(self, message):
        self.socketio.emit("transport_log", {"message": message})
