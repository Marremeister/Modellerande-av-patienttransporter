import eventlet
from eventlet.semaphore import Semaphore
from ilp_optimizer_strategy import ILPOptimizerStrategy
from model_transportation_request import TransportationRequest
from assignment_strategy import AssignmentStrategy

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
        self.simulation = None
        self.assignment_strategy: AssignmentStrategy = ILPOptimizerStrategy()

    def set_strategy(self, strategy: AssignmentStrategy):
        """Dynamically update the assignment strategy (ILP or Random etc)."""
        self.assignment_strategy = strategy
        strategy_name = strategy.__class__.__name__
        self.socketio.emit("transport_log", {
            "message": f"⚙️ Assignment strategy switched to: {strategy_name}"
        })
        print(f"🔄 Assignment strategy switched to: {strategy_name}")

    def deploy_strategy_assignment(self):
        """Triggers the active assignment strategy to be deployed in a background thread."""
        print("🚀 DEBUG: Deploying assignment strategy...")
        eventlet.spawn_n(self.execute_assignment_plan)
        return {"status": "🚀 Assignment strategy deployed!"}

    def execute_assignment_plan(self):
        """
        Uses the current assignment strategy (ILP, Random, etc) to assign transport requests.
        Preserves ongoing tasks, clears old queues, and populates new queues.
        """
        self.socketio.emit("transport_log", {"message": "🔁 Re-optimizing all transport assignments..."})

        transporters = self.get_transporter_objects()
        pending_requests = self.pending_requests
        graph = self.hospital.get_graph()

        self.socketio.emit("transport_log", {
            "message": f"📦 Found {len(pending_requests)} pending requests."
        })

        resting = sum(1 for t in transporters if t.shift_manager.resting)
        busy = sum(1 for t in transporters if t.is_busy)
        idle = len(transporters) - resting - busy

        self.socketio.emit("transport_log", {
            "message": f"🧍 Transporter Status — Resting: {resting}, Busy: {busy}, Idle: {idle}"
        })

        assignment_plan = self.assignment_strategy.generate_assignment_plan(transporters, pending_requests, graph)

        if not assignment_plan:
            self.socketio.emit("transport_log", {
                "message": "❌ Optimization failed or no assignments available."
            })
            return

        optimizer = None
        if isinstance(self.assignment_strategy, ILPOptimizerStrategy):
            from ilp_optimizer import ILPOptimizer
            optimizer = ILPOptimizer(transporters, pending_requests, graph)

        for transporter in self.transporters:
            assigned_requests = assignment_plan.get(transporter.name, [])

            if transporter.shift_manager.resting:
                self.socketio.emit("transport_log", {
                    "message": f"💤 {transporter.name} is currently resting and will not be assigned new requests."
                })
                transporter.task_queue = assigned_requests
                continue

            if transporter.is_busy and transporter.current_task:
                self.socketio.emit("transport_log", {
                    "message": f"🔒 Preserving current task for {transporter.name}: "
                               f"{transporter.current_task.origin} ➝ {transporter.current_task.destination}"
                })

                current_req = transporter.current_task

                # 🧠 Avoid re-assigning the same request that's already ongoing
                assigned_requests = [
                    req for req in assigned_requests
                    if not (req.origin == current_req.origin and req.destination == current_req.destination)
                ]

                # 🔁 Queue is safely updated; current task continues
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

        # 📝 Task summary logging
        for transporter in self.transporters:
            self.socketio.emit("transport_log", {
                "message": f"📝 {transporter.name} task summary:"
            })

            total_duration = 0

            if transporter.current_task:
                duration = optimizer.estimate_travel_time(transporter, transporter.current_task) if optimizer else "-"
                total_duration += duration if isinstance(duration, (int, float)) else 0
                self.socketio.emit("transport_log", {
                    "message": f"   🔄 In progress: {transporter.current_task.origin} ➝ {transporter.current_task.destination} (⏱️ ~{duration:.1f}s)" if isinstance(
                        duration, (int,
                                   float)) else f"   🔄 In progress: {transporter.current_task.origin} ➝ {transporter.current_task.destination}"
                })

            if transporter.task_queue:
                for i, queued in enumerate(transporter.task_queue):
                    duration = optimizer.estimate_travel_time(transporter, queued) if optimizer else "-"
                    total_duration += duration if isinstance(duration, (int, float)) else 0
                    self.socketio.emit("transport_log", {
                        "message": f"   ⏳ Queued[{i + 1}]: {queued.origin} ➝ {queued.destination} (⏱️ ~{duration:.1f}s)" if isinstance(
                            duration, (int, float)) else f"   ⏳ Queued[{i + 1}]: {queued.origin} ➝ {queued.destination}"
                    })

            if total_duration > 0:
                self.socketio.emit("transport_log", {
                    "message": f"⏱️ Estimated total completion time for {transporter.name}: ~{total_duration:.1f} seconds"
                })
            elif not transporter.current_task:
                self.socketio.emit("transport_log", {
                    "message": f"   💤 Idle"
                })

    def add_transporter(self, transporter):
        transporter.current_location = "Transporter Lounge"
        transporter.task_queue = []
        transporter.current_task = None
        transporter.is_busy = False

        self.transporters.append(transporter)

        print(f"🚑 Transporter {transporter.name} added.")
        self.socketio.emit("new_transporter", {
            "name": transporter.name,
            "status": transporter.status,
            "current_location": transporter.current_location
        })

        self.socketio.emit("transport_log", {
            "message": f"🆕 {transporter.name} added at {transporter.current_location} and is ready for assignments."
        })

        # ✅ Trigger reoptimization if there are pending tasks
        if self.pending_requests:
            self.deploy_strategy_assignment()

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
            eventlet.spawn_n(self.process_transport, transporter, request_obj)


        return {
            "status": f"✅ {transporter.name} is transporting {request_obj.transport_type} from {request_obj.origin} to {request_obj.destination}."}

    def process_transport(self, transporter, request):
        """Handles a transport assignment step-by-step, including rest handling."""
        self.socketio.emit("transport_log", {
            "message": f"🛫 {transporter.name} started transport from {request.origin} to {request.destination}."
        })

        # Step 1: Move to origin
        if not transporter.move_to(request.origin):
            self.socketio.emit("transport_log", {
                "message": f"❌ {transporter.name} failed to reach {request.origin}."
            })
            return

        # Step 2: Move to destination
        if not transporter.move_to(request.destination):
            self.socketio.emit("transport_log", {
                "message": f"❌ {transporter.name} failed to reach {request.destination}."
            })
            return

        # Step 3: Complete transport
        request.status = "completed"
        if request in self.ongoing_requests:
            self.ongoing_requests.remove(request)
        if request in self.pending_requests:
            self.pending_requests.remove(request)

        self.completed_requests.append(request)

        self.socketio.emit("transport_log", {
            "message": f"🏁 {transporter.name} completed transport from {request.origin} to {request.destination}."
        })

        self.socketio.emit("transport_completed", {
            "transporter": transporter.name,
            "origin": request.origin,
            "destination": request.destination
        })

        # Step 4: Workload cooldown
        eventlet.spawn_n(transporter.reduce_workload)

        # Step 5: Mandatory rest check
        if transporter.shift_manager.should_rest():
            self.socketio.emit("transport_log", {
                "message": f"😴 {transporter.name} has reached their limit and is heading to the lounge for rest."
            })

            transporter.shift_manager.begin_rest()
            transporter.move_to("Transporter Lounge")
            eventlet.sleep(transporter.shift_manager.rest_duration)
            transporter.shift_manager.end_rest()

            self.socketio.emit("transport_log", {
                "message": f"☀️ {transporter.name} is now rested and ready for new assignments!"
            })
            if self.simulation and self.simulation.is_running():
                eventlet.spawn_n(self.execute_assignment_plan)

        # Step 6: Continue with next task if available
        if transporter.task_queue:
            next_request = transporter.task_queue.pop(0)
            transporter.current_task = next_request
            self.ongoing_requests.append(next_request)
            next_request.status = "ongoing"
            eventlet.spawn_n(self.process_transport, transporter, next_request)
        else:
            transporter.current_task = None
            transporter.is_busy = False

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

    def set_simulation_state(self, running: bool):
        self.simulation_running = running

