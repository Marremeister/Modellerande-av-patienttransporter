def _run_optimization(self):
    """
    Runs ILP optimization and reassigns all pending transport requests.
    Preserves in-progress tasks but replaces queued tasks with a new optimized plan.
    Sends detailed logs to the frontend via transport_log socket events, including estimated durations.
    """
    self.socketio.emit("transport_log", {"message": "🔁 Re-optimizing all transport assignments..."})

    transporters = self.get_transporter_objects()
    pending_requests = self.pending_requests
    graph = self.hospital.get_graph()

    optimizer = ILPOptimizer(transporters, pending_requests, graph)
    assignment_plan = optimizer.generate_assignment_plan()

    if not assignment_plan:
        self.socketio.emit("transport_log", {
            "message": "❌ Optimization failed or no assignments available."
        })
        return

    for transporter in self.transporters:
        assigned_requests = assignment_plan.get(transporter.name, [])

        # ⛔ Skip if transporter is resting
        if transporter.shift_manager.resting:
            self.socketio.emit("transport_log", {
                "message": f"💤 {transporter.name} is currently resting and will not be assigned new requests."
            })
            transporter.task_queue = assigned_requests  # Pre-queue
            continue

        if transporter.is_busy and transporter.current_task:
            self.socketio.emit("transport_log", {
                "message": f"🔒 Preserving current task for {transporter.name}: "
                           f"{transporter.current_task.origin} ➝ {transporter.current_task.destination}"
            })
            transporter.task_queue = assigned_requests

        elif assigned_requests:
            first = assigned_requests.pop(0)
            transporter.current_task = first
            transporter.is_busy = True
            first.status = "ongoing"
            self.ongoing_requests.append(first)

            self.socketio.emit("transport_log", {
                "message": f"🚑 Assigned {transporter.name} to: {first.origin} ➝ {first.destination}"
            })

            transporter.task_queue = assigned_requests
            eventlet.spawn_n(self.process_transport, transporter, first)

        else:
            transporter.current_task = None
            transporter.task_queue = []
            transporter.is_busy = False
            self.socketio.emit("transport_log", {
                "message": f"✅ {transporter.name} is idle."
            })

    # 📝 Summary logs
    for transporter in self.transporters:
        self.socketio.emit("transport_log", {
            "message": f"📝 {transporter.name} task summary:"
        })

        total_duration = 0

        if transporter.current_task:
            duration = optimizer.estimate_travel_time(transporter, transporter.current_task)
            total_duration += duration
            self.socketio.emit("transport_log", {
                "message": f"   🔄 In progress: {transporter.current_task.origin} ➝ {transporter.current_task.destination} (⏱️ ~{duration:.1f}s)"
            })

        if transporter.task_queue:
            for i, queued in enumerate(transporter.task_queue):
                duration = optimizer.estimate_travel_time(transporter, queued)
                total_duration += duration
                self.socketio.emit("transport_log", {
                    "message": f"   ⏳ Queued[{i + 1}]: {queued.origin} ➝ {queued.destination} (⏱️ ~{duration:.1f}s)"
                })

        if total_duration > 0:
            self.socketio.emit("transport_log", {
                "message": f"⏱️ Estimated total completion time for {transporter.name}: ~{total_duration:.1f}s"
            })
        elif not transporter.current_task:
            self.socketio.emit("transport_log", {
                "message": f"   💤 Idle"
            })