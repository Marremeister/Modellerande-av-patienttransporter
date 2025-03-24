from Model.model_transportation_request import TransportationRequest
from Model.transport_assignment_handler import TransportAssignmentHandler

class AssignmentExecutor:
    def __init__(self, transport_manager, socketio, strategy, assignable_requests=None):
        self.tm = transport_manager
        self.socketio = socketio
        self.strategy = strategy
        self.assignable_requests = assignable_requests
        self.handler = TransportAssignmentHandler(socketio, transport_manager)

    def run(self):
        self._emit_reoptimization_start()

        transporters = self.tm.get_transporter_objects()
        all_requests = self.assignable_requests or TransportationRequest.get_assignable_requests()
        graph = self.tm.hospital.get_graph()

        self._emit_pending_status(all_requests)
        self._emit_transporter_status(transporters)

        assignment_plan = self.strategy.generate_assignment_plan(transporters, all_requests, graph)
        if not assignment_plan:
            self._emit_no_assignment_found()
            return

        optimizer = self.strategy.get_optimizer(transporters, all_requests, graph)

        for transporter in transporters:
            self._assign_tasks_to_transporter(transporter, assignment_plan, optimizer)

        self._log_summary_for_all(optimizer)

    def _assign_tasks_to_transporter(self, transporter, assignment_plan, optimizer):
        assigned_requests = assignment_plan.get(transporter.name, [])

        if transporter.shift_manager.resting:
            self._log(f"💤 {transporter.name} is resting. Skipping assignment.")
            transporter.task_queue = assigned_requests
            return

        if transporter.is_busy and transporter.current_task:
            self._preserve_current_task(transporter, assigned_requests)
        elif assigned_requests:
            first = assigned_requests.pop(0)
            self.handler.assign(transporter, first)
            transporter.task_queue = assigned_requests
        else:
            self._mark_transporter_idle(transporter)

    def _preserve_current_task(self, transporter, assigned_requests):
        self._log(f"🔒 Preserving current task for {transporter.name}")
        current_req = transporter.current_task

        filtered = [
            r for r in assigned_requests
            if not (r.origin == current_req.origin and r.destination == current_req.destination)
        ]
        transporter.task_queue = filtered

    def _mark_transporter_idle(self, transporter):
        transporter.current_task = None
        transporter.task_queue = []
        transporter.is_busy = False
        self._log(f"✅ {transporter.name} is idle.")

    def _log_summary_for_all(self, optimizer):
        for transporter in self.tm.transporters:
            self._log(f"📝 {transporter.name} task summary:")
            self._log_transporter_summary(transporter, optimizer)

    def _log_transporter_summary(self, transporter, optimizer):
        total_duration = 0

        if transporter.current_task:
            dur = self._estimate(transporter, transporter.current_task, optimizer)
            total_duration += dur if isinstance(dur, (int, float)) else 0
            self._emit_task("🔄 In progress", transporter.current_task, dur)

        for i, task in enumerate(transporter.task_queue):
            dur = self._estimate(transporter, task, optimizer)
            total_duration += dur if isinstance(dur, (int, float)) else 0
            self._emit_task(f"⏳ Queued[{i + 1}]", task, dur)

        if total_duration:
            self._log(f"⏱️ Estimated total completion for {transporter.name}: ~{total_duration:.1f}s")
        elif not transporter.current_task:
            self._log("   💤 Idle")

    def _estimate(self, transporter, request, optimizer):
        return optimizer.estimate_travel_time(transporter, request) if optimizer else "-"

    def _emit_task(self, prefix, task, duration):
        msg = f"   {prefix}: {task.origin} ➝ {task.destination}"
        if isinstance(duration, (int, float)):
            msg += f" (⏱️ ~{duration:.1f}s)"
        self._log(msg)

    def _emit_reoptimization_start(self):
        self._log("🔁 Re-optimizing all transport assignments...")

    def _emit_pending_status(self, requests):
        self._log(f"📦 Found {len(requests)} pending requests.")

    def _emit_transporter_status(self, transporters):
        resting = sum(t.shift_manager.resting for t in transporters)
        busy = sum(t.is_busy for t in transporters)
        idle = len(transporters) - resting - busy
        self._log(f"🧍 Transporter Status — Resting: {resting}, Busy: {busy}, Idle: {idle}")

    def _emit_no_assignment_found(self):
        self._log("❌ Optimization failed or no assignments available.")

    def _log(self, message):
        self.socketio.emit("transport_log", {"message": message})
