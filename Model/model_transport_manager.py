import eventlet

from Model.Assignment_strategies.ILP.ilp_optimizer_strategy import ILPOptimizerStrategy
from Model.Assignment_strategies.assignment_strategy import AssignmentStrategy
from Model.assignment_executor import AssignmentExecutor
from Model.model_transportation_request import TransportationRequest

class TransportManager:
    def __init__(self, hospital, socketio):
        self.hospital = hospital
        self.socketio = socketio
        self.transporters = []
        self.simulation = None
        self.assignment_strategy: AssignmentStrategy = ILPOptimizerStrategy()

    def set_strategy(self, strategy: AssignmentStrategy):
        self.assignment_strategy = strategy
        strategy_name = strategy.__class__.__name__
        self.socketio.emit("transport_log", {
            "message": f"⚙️ Assignment strategy switched to: {strategy_name}"
        })
        print(f"🔄 Assignment strategy switched to: {strategy_name}")

    def deploy_strategy_assignment(self):
        print("🚀 DEBUG: Deploying assignment strategy...")
        eventlet.spawn_n(self.execute_assignment_plan)
        return {"status": "🚀 Assignment strategy deployed!"}

    def execute_assignment_plan(self):
        assignable_requests = TransportationRequest.get_assignable_requests()  # ✅ Gather reassignable ones
        executor = AssignmentExecutor(self, self.socketio, self.assignment_strategy, assignable_requests)
        executor.run()

    def get_assignable_requests(self):
        # ✅ Collect all reassignable requests from pending + task queues
        assignable = set(r for r in TransportationRequest.pending_requests if r.is_reassignable())

        for transporter in self.transporters:
            for r in transporter.task_queue:
                if r.is_reassignable():
                    assignable.add(r)

        return list(assignable)

    def has_assignable_work(self):
        if any(r.is_reassignable() for r in TransportationRequest.pending_requests):
            return True
        for transporter in self.transporters:
            if any(r.is_reassignable() for r in transporter.task_queue):
                return True
        return False

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

        if self.has_assignable_work():
            self.socketio.emit("transport_log", {
                "message": f"🔁 Re-optimizing all assignments after adding {transporter.name}"
            })
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

        if request_obj not in TransportationRequest.pending_requests:
            print(
                f"❌ ERROR: Transport Request {request_obj.origin} → {request_obj.destination} NOT FOUND in pending_requests")
            return {"error": "Transport request not found or already assigned"}, 400

        # Move request to ongoing
        request_obj.mark_as_ongoing()

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

        request.mark_as_completed()

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
            next_request.mark_as_ongoing()
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
        request = TransportationRequest.create(origin, destination, transport_type, urgent)
        return request

    def remove_transport_request(self, request_key):
        """Removes a transport request from completed requests."""
        TransportationRequest.remove_completed_request(request_key)
        return {"status": f"Request {request_key} removed."}

    def get_transport_requests(self):
        """Returns all transport requests categorized by status."""
        return TransportationRequest.get_requests()

    def set_simulation_state(self, running: bool):
        self.simulation_running = running

    def has_assignable_work(self):
        if TransportationRequest.pending_requests:
            return True
        for transporter in self.transporters:
            if transporter.task_queue:
                return True
        return False

