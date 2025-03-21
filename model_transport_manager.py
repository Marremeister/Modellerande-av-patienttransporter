import eventlet
from eventlet.semaphore import Semaphore
from ilp_optimizer import ILPOptimizer
from model_transportation_request import TransportationRequest

class TransportManager:
    def __init__(self, hospital, socketio):
        """Handles transport assignments and manages transporters."""
        self.hospital = hospital
        self.socketio = socketio
        self.transporters = []
        self.pending_requests = []
        self.ongoing_requests = []
        self.completed_requests = []
        self.transport_lock = Semaphore()  # Prevents simultaneous modifications

    def deploy_optimization(self):
        """Runs ILP optimization and assigns transporters in parallel, without blocking the main event loop."""
        print("🚀 DEBUG: Deploying Optimization...")

        # ✅ Run optimization in a background thread to prevent UI lag
        eventlet.spawn_n(self._run_optimization)

        return {"status": "🚀 Optimization started! Transporters will move shortly."}

    def _run_optimization(self):
        """
        Runs ILP optimization and reassigns all pending transport requests.
        Preserves in-progress tasks but replaces all queued tasks with a new optimal plan.
        Sends detailed logs to the frontend via transport_log socket events.
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

        # 🔄 Reset all transporters
        for transporter in self.transporters:
            assigned_requests = assignment_plan.get(transporter.name, [])

            if transporter.is_busy and transporter.current_task:
                self.socketio.emit("transport_log", {
                    "message": f"🔒 Preserving current task for {transporter.name}: "
                               f"{transporter.current_task.origin} ➝ {transporter.current_task.destination}"
                })
                transporter.task_queue = assigned_requests  # Just queue the new optimized tasks
            elif assigned_requests:
                # Assign first request now, queue the rest
                first = assigned_requests.pop(0)
                transporter.current_task = first
                transporter.is_busy = True
                self.ongoing_requests.append(first)
                first.status = "ongoing"

                self.socketio.emit("transport_log", {
                    "message": f"🚑 Assigned {transporter.name} to: {first.origin} ➝ {first.destination}"
                })

                transporter.task_queue = assigned_requests
                eventlet.spawn_n(self.process_transport, transporter)
            else:
                # No task at all
                transporter.current_task = None
                transporter.task_queue = []
                transporter.is_busy = False
                self.socketio.emit("transport_log", {
                    "message": f"✅ {transporter.name} is idle."
                })

        # 📝 Summary log for each transporter
        for transporter in self.transporters:
            self.socketio.emit("transport_log", {
                "message": f"📝 {transporter.name} task summary:"
            })

            if transporter.current_task:
                self.socketio.emit("transport_log", {
                    "message": f"   🔄 In progress: {transporter.current_task.origin} ➝ {transporter.current_task.destination}"
                })

            if transporter.task_queue:
                for i, queued in enumerate(transporter.task_queue):
                    self.socketio.emit("transport_log", {
                        "message": f"   ⏳ Queued[{i + 1}]: {queued.origin} ➝ {queued.destination}"
                    })
            else:
                if not transporter.current_task:
                    self.socketio.emit("transport_log", {
                        "message": f"   💤 Idle"
                    })

    def add_transporter(self, transporter):
        """Adds a new transporter to the system."""
        self.transporters.append(transporter)
        print(f"🚑 Transporter {transporter.name} added.")
        self.socketio.emit("new_transporter", {"name": transporter.name, "status": transporter.status})

    def get_transporter(self, name):
        """Finds a transporter by name."""
        return next((t for t in self.transporters if t.name == name), None)


    def get_transporters(self):
        """Returns a list of available transporters with their current locations."""
        return [{
            "name": t.name,
            "current_location": t.current_location,
            "status": t.status  # Ensure status is sent
        } for t in self.transporters]

    def get_transporter_objects(self):
        """Returns transporters as Python objects for internal processing."""
        return self.transporters  # ✅ Returns list of PatientTransporter instances

    def set_transporter_status(self, name, status):
        """Updates a transporter's status."""
        transporter = self.get_transporter(name)
        if not transporter:
            return {"error": f"🚫 Transporter {name} not found"}

        if status == "active":
            transporter.set_active()
        else:
            transporter.set_inactive()

        return {"status": f"🔄 {name} is now {status}"}

    def assign_transport(self, transporter_name, request_obj):
        """Assigns a transport request to a transporter and moves them step-by-step."""
        transporter = self.get_transporter(transporter_name)

        print(
            f"🚀 DEBUG: assign_transport called for {transporter_name} to handle {request_obj.origin} → {request_obj.destination}")

        if not transporter:
            print(f"❌ ERROR: Transporter {transporter_name} NOT FOUND in transport manager!")
            return {"error": f"Transporter {transporter_name} not found"}, 400

        if transporter.status == "inactive":
            print(f"❌ ERROR: Transporter {transporter.name} is INACTIVE")
            return {"error": f"❌ {transporter.name} is inactive and cannot be assigned a task."}, 400

        if request_obj not in self.pending_requests:
            print(
                f"❌ ERROR: Transport Request {request_obj.origin} → {request_obj.destination} NOT FOUND in pending_requests")
            return {"error": "Transport request not found or already assigned"}, 400

        # Move request to ongoing
        self.pending_requests.remove(request_obj)
        self.ongoing_requests.append(request_obj)
        request_obj.status = "ongoing"

        print(f"🚑 {transporter.name} assigned transport: {request_obj.origin} ➝ {request_obj.destination}")

        # Emit update to frontend
        self.socketio.emit("transport_status_update", {
            "status": "ongoing",
            "request": {
                "origin": request_obj.origin,
                "destination": request_obj.destination,
                "transport_type": request_obj.transport_type
            }
        })

        # Move transporter step-by-step
        if transporter.is_busy:
            transporter.task_queue.append(request_obj)
            print(f"🕒 {transporter.name} is busy. Queued transport {request_obj.origin} → {request_obj.destination}")
            self.socketio.emit("transport_log", {
                "message": f"🕒 {transporter.name} is busy. Queued transport {request_obj.origin} → {request_obj.destination}"
            })
        else:
            transporter.current_task = request_obj
            transporter.is_busy = True
            eventlet.spawn_n(self.process_transport, transporter)

        return {
            "status": f"✅ {transporter.name} is transporting {request_obj.transport_type} from {request_obj.origin} to {request_obj.destination}."}

    def process_transport(self, transporter):
        request = transporter.current_task
        if not request:
            print(f"⚠️ No current task found for {transporter.name}. Skipping.")
            transporter.is_busy = False
            return

        print(f"🚀 {transporter.name} starting transport {request.origin} ➝ {request.destination}")

        # Step 1: Move to pickup location
        success = transporter.move_to(request.origin)
        if not success:
            print(f"❌ {transporter.name} failed to reach {request.origin}")
            transporter.is_busy = False
            transporter.current_task = None
            return

        # Step 2: Move to destination
        success = transporter.move_to(request.destination)
        if not success:
            print(f"❌ {transporter.name} failed to reach {request.destination}")
            transporter.is_busy = False
            transporter.current_task = None
            return

        # Step 3: Mark task as completed
        if request in self.ongoing_requests:
            self.ongoing_requests.remove(request)
            self.completed_requests.append(request)
            request.status = "completed"

        print(f"🏁 {transporter.name} completed transport: {request.origin} ➝ {request.destination}")

        # Notify frontend
        self.socketio.emit("transport_completed", {
            "transporter": transporter.name,
            "origin": request.origin,
            "destination": request.destination
        })
        self.socketio.emit("transport_log", {
            "message": f"✅ {transporter.name} completed transport from {request.origin} to {request.destination}"
        })

        # Step 4: Clear current task
        transporter.current_task = None
        transporter.is_busy = False

        # Step 5: Start next queued task if available
        if transporter.task_queue:
            next_task = transporter.task_queue.pop(0)
            transporter.current_task = next_task
            transporter.is_busy = True
            print(f"🔁 {transporter.name} starting next queued task: {next_task.origin} ➝ {next_task.destination}")
            eventlet.spawn_n(self.process_transport, transporter)

        # Step 6: Optional workload reduction
        eventlet.spawn_n(transporter.reduce_workload)

    def return_home(self, transporter_name):
        """Returns a transporter to the Transporter Lounge."""
        transporter = self.get_transporter(transporter_name)

        if not transporter:
            return {"error": f"Transporter {transporter_name} not found"}, 400

        if transporter.current_location == "Transporter Lounge":
            return {"status": f"{transporter_name} is already in the lounge."}

        # Calculate path to lounge
        path_to_lounge, _ = transporter.pathfinder.dijkstra(transporter.current_location, "Transporter Lounge")

        if not path_to_lounge:
            return {"error": f"No valid path to Transporter Lounge for {transporter_name}"}, 400

        # Move transporter
        transporter.move_to("Transporter Lounge")

        return {"status": f"{transporter_name} has returned to the lounge."}

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        """Creates and stores a transport request."""
        request = TransportationRequest(origin, destination, transport_type, urgent)
        self.pending_requests.append(request)  # 🔥 Store in pending list

        print(f"📦 New Transport Request: {origin} → {destination} (Type: {transport_type}, Urgent: {urgent})")

        return request

    def remove_transport_request(self, request_key):
        """Removes a transport request from completed requests."""
        self.completed_requests = [r for r in self.completed_requests if f"{r.origin}-{r.destination}" != request_key]
        return {"status": f"Request {request_key} removed."}

    def get_transport_requests(self):
        """Returns all transport requests categorized by status."""
        return {
            "pending": [vars(r) for r in self.pending_requests],
            "ongoing": [vars(r) for r in self.ongoing_requests],
            "completed": [vars(r) for r in self.completed_requests]
        }



