import eventlet
from Model.model_transportation_request import TransportationRequest


class AssignmentExecutor:
    def __init__(self, transport_manager, socketio, strategy, assignable_requests=None):
        self.tm = transport_manager
        self.socketio = socketio
        self.strategy = strategy
        self.assignable_requests = assignable_requests  # ✅ Optional override

    def run(self):
        self._emit_reoptimization_start()

        transporters = self.tm.get_transporter_objects()
        all_requests = self.assignable_requests or TransportationRequest.get_assignable_requests()

        graph = self.tm.hospital.get_graph()

        self._emit_pending_status(all_requests)
        self._emit_transporter_status(transporters)

        assignment_plan = self.strategy.generate_assignment_plan(
            transporters, all_requests, graph
        )

        if not assignment_plan:
            self._emit_no_assignment_found()
            return

        optimizer = self.strategy.get_optimizer(transporters, all_requests, graph)

        for transporter in transporters:
            self._assign_tasks_to_transporter(transporter, assignment_plan, optimizer)

        self._log_summary_for_all(optimizer)

    # --- Assignment Logic ---

    def _assign_tasks_to_transporter(self, transporter, assignment_plan, optimizer):
        assigned_requests = assignment_plan.get(transporter.name, [])

        if transporter.shift_manager.resting:
            self.socketio.emit("transport_log", {
                "message": f"💤 {transporter.name} is currently resting and will not be assigned new requests."
            })
            transporter.task_queue = assigned_requests
            return

        if transporter.is_busy and transporter.current_task:
            self._preserve_current_task(transporter, assigned_requests)
        elif assigned_requests:
            self._start_new_task(transporter, assigned_requests, optimizer)
        else:
            self._mark_transporter_idle(transporter)

    def _preserve_current_task(self, transporter, assigned_requests):
        self.socketio.emit("transport_log", {
            "message": f"🔒 Preserving current task for {transporter.name}: "
                       f"{transporter.current_task.origin} ➝ {transporter.current_task.destination}"
        })

        current_req = transporter.current_task
        filtered = [
            req for req in assigned_requests
            if not (req.origin == current_req.origin and req.destination == current_req.destination)
        ]

        transporter.task_queue = filtered

    def _start_new_task(self, transporter, assigned_requests, optimizer):
        first = assigned_requests.pop(0)
        transporter.current_task = first
        transporter.is_busy = True

        # ✅ Centralized tracking
        first.mark_as_ongoing()

        self.socketio.emit("transport_log", {
            "message": f"🚑 Assigned {transporter.name} to: {first.origin} ➝ {first.destination}"
        })

        transporter.task_queue = assigned_requests
        eventlet.spawn_n(self.tm.process_transport, transporter, first)

    def _mark_transporter_idle(self, transporter):
        transporter.current_task = None
        transporter.task_queue = []
        transporter.is_busy = False

        self.socketio.emit("transport_log", {
            "message": f"✅ {transporter.name} is idle."
        })

    # --- Summary Logging ---

    def _log_summary_for_all(self, optimizer):
        for transporter in self.tm.transporters:
            self.socketio.emit("transport_log", {
                "message": f"📝 {transporter.name} task summary:"
            })
            self._log_transporter_summary(transporter, optimizer)

    def _log_transporter_summary(self, transporter, optimizer):
        total_duration = 0

        if transporter.current_task:
            duration = self._estimate(transporter, transporter.current_task, optimizer)
            total_duration += duration if isinstance(duration, (int, float)) else 0
            self._emit_task_status("🔄 In progress", transporter.current_task, duration)

        for i, task in enumerate(transporter.task_queue):
            duration = self._estimate(transporter, task, optimizer)
            total_duration += duration if isinstance(duration, (int, float)) else 0
            self._emit_task_status(f"⏳ Queued[{i + 1}]", task, duration)

        if total_duration > 0:
            self.socketio.emit("transport_log", {
                "message": f"⏱️ Estimated total completion time for {transporter.name}: ~{total_duration:.1f} seconds"
            })
        elif not transporter.current_task:
            self.socketio.emit("transport_log", {"message": f"   💤 Idle"})

    def _estimate(self, transporter, task, optimizer):
        if optimizer:
            return optimizer.estimate_travel_time(transporter, task)
        return "-"

    def _emit_task_status(self, prefix, task, duration):
        if isinstance(duration, (int, float)):
            msg = f"   {prefix}: {task.origin} ➝ {task.destination} (⏱️ ~{duration:.1f}s)"
        else:
            msg = f"   {prefix}: {task.origin} ➝ {task.destination}"

        self.socketio.emit("transport_log", {"message": msg})

    # --- Helper Emitters ---

    def _emit_reoptimization_start(self):
        self.socketio.emit("transport_log", {"message": "🔁 Re-optimizing all transport assignments..."})

    def _emit_pending_status(self, pending_requests):
        self.socketio.emit("transport_log", {
            "message": f"📦 Found {len(pending_requests)} pending requests."
        })

    def _emit_transporter_status(self, transporters):
        resting = sum(1 for t in transporters if t.shift_manager.resting)
        busy = sum(1 for t in transporters if t.is_busy)
        idle = len(transporters) - resting - busy

        self.socketio.emit("transport_log", {
            "message": f"🧍 Transporter Status — Resting: {resting}, Busy: {busy}, Idle: {idle}"
        })

    def _emit_no_assignment_found(self):
        self.socketio.emit("transport_log", {
            "message": "❌ Optimization failed or no assignments available."
        })
