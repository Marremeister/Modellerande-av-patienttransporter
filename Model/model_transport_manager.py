import eventlet
from Model.Assignment_strategies.ILP.ilp_optimizer_strategy import ILPOptimizerStrategy
from Model.Assignment_strategies.assignment_strategy import AssignmentStrategy
from Model.assignment_executor import AssignmentExecutor
from Model.model_transportation_request import TransportationRequest
from Model.transport_assignment_handler import TransportAssignmentHandler
from Model.Assignment_strategies.strategy_registry import STRATEGY_REGISTRY
from Model.simulation_state import SimulationState


class TransportManager:
    def __init__(self, hospital, socketio):
        self.hospital = hospital
        self.socketio = socketio
        self.transporters = []
        self.simulation = None
        self.assignment_strategy: AssignmentStrategy = ILPOptimizerStrategy()
        self.assignment_handler = TransportAssignmentHandler(socketio, self)
        self.simulation_running = False
        self.state = SimulationState.READY

    def set_state(self, new_state, emit_notification=True):
        """Change the system state with proper notification"""
        old_state = self.state
        self.state = new_state

        if emit_notification:
            self.socketio.emit("system_state_change", {
                "previous": old_state.value,
                "current": new_state.value
            })
        return old_state

    def set_simulation_state(self, running: bool):
        """Central method to update simulation state"""
        self.simulation_running = running
        if running:
            self.set_state(SimulationState.RUNNING)
        else:
            self.set_state(SimulationState.READY)

        # This method now becomes a central place for all simulation state changes

    def set_strategy_by_name(self, name: str):
        factory = STRATEGY_REGISTRY.get(name)
        if not factory:
            return {"error": f"❌ Unknown strategy: {name}"}, 400
        self._set_strategy(factory())
        return {"status": f"✅ Strategy set to: {name}"}

    def _set_strategy(self, strategy: AssignmentStrategy):
        self.assignment_strategy = strategy
        self.socketio.emit("transport_log", {
            "message": f"⚙️ Assignment strategy switched to: {strategy.__class__.__name__}"
        })

    def get_available_strategy_names(self):
        return list(STRATEGY_REGISTRY.keys())

    def deploy_strategy_assignment(self):
        eventlet.spawn_n(self.execute_assignment_plan)
        return {"status": "🚀 Assignment strategy deployed!"}

    def execute_assignment_plan(self):
        assignable_requests = TransportationRequest.get_assignable_requests()
        executor = AssignmentExecutor(self, self.socketio, self.assignment_strategy, assignable_requests)
        executor.run()

    def get_assignable_requests(self):
        assignable = set(r for r in TransportationRequest.pending_requests if r.is_reassignable())
        for t in self.transporters:
            assignable.update(r for r in t.task_queue if r.is_reassignable())
        return list(assignable)

    def has_assignable_work(self):
        return any(r.is_reassignable() for r in TransportationRequest.pending_requests) or any(
            r.is_reassignable() for t in self.transporters for r in t.task_queue)

    def add_transporter(self, transporter):
        transporter.current_location = "Transporter Lounge"
        transporter.task_queue = []
        transporter.current_task = None
        transporter.is_busy = False

        self.transporters.append(transporter)
        self.socketio.emit("new_transporter", transporter.to_dict())

        self.socketio.emit("transport_log", {
            "message": f"🆕 {transporter.name} added at {transporter.current_location} and is ready for assignments."
        })

        # Only auto-deploy if in RUNNING state and we have assignable work
        if self.state == SimulationState.RUNNING and self.has_assignable_work():
            self.socketio.emit("transport_log", {
                "message": f"🔁 Re-optimizing all assignments after adding {transporter.name}"
            })
            self.deploy_strategy_assignment()

    def get_transporter(self, name):
        return next((t for t in self.transporters if t.name == name), None)

    def get_transporter_objects(self):
        return self.transporters

    def get_transporters(self):
        return [{"name": t.name, "current_location": t.current_location, "status": t.status} for t in self.transporters]

    def set_transporter_status(self, name, status):
        t = self.get_transporter(name)
        if not t:
            return {"error": f"🚫 Transporter {name} not found"}
        t.set_active() if status == "active" else t.set_inactive()
        return {"status": f"🔄 {name} is now {status}"}

    def assign_transport(self, transporter_name, request_obj):
        transporter = self.get_transporter(transporter_name)

        if not transporter:
            return {"error": f"Transporter {transporter_name} not found"}, 400
        if transporter.status == "inactive":
            return {"error": f"❌ {transporter.name} is inactive and cannot be assigned a task."}, 400
        if request_obj not in TransportationRequest.pending_requests:
            return {"error": "Transport request not found or already assigned"}, 400

        self.assignment_handler.assign(transporter, request_obj)
        return {
            "status": f"✅ {transporter.name} is transporting {request_obj.transport_type} from {request_obj.origin} to {request_obj.destination}."
        }

    def process_transport(self, transporter, request):
        self.socketio.emit("transport_log", {
            "message": f"🛫 {transporter.name} started transport from {request.origin} to {request.destination}."
        })

        if not transporter.move_to(request.origin):
            self.socketio.emit("transport_log", {"message": f"❌ {transporter.name} failed to reach {request.origin}."})
            return

        if not transporter.move_to(request.destination):
            self.socketio.emit("transport_log", {"message": f"❌ {transporter.name} failed to reach {request.destination}."})
            return

        request.mark_as_completed()
        self.socketio.emit("transport_log", {
            "message": f"🏁 {transporter.name} completed transport from {request.origin} to {request.destination}."
        })
        self.socketio.emit("transport_completed", {
            "transporter": transporter.name,
            "origin": request.origin,
            "destination": request.destination
        })

        eventlet.spawn_n(transporter.reduce_workload)

        if transporter.shift_manager.should_rest():
            self.socketio.emit("transport_log", {
                "message": f"😴 {transporter.name} has reached their limit and is heading to rest."
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

        if transporter.task_queue:
            next_request = transporter.task_queue.pop(0)
            transporter.current_task = next_request
            next_request.mark_as_ongoing()
            eventlet.spawn_n(self.process_transport, transporter, next_request)
        else:
            transporter.current_task = None
            transporter.is_busy = False

    def return_home(self, transporter_name):
        transporter = self.get_transporter(transporter_name)
        if not transporter:
            return {"error": f"Transporter {transporter_name} not found"}, 400
        if transporter.current_location == "Transporter Lounge":
            return {"status": f"{transporter_name} is already in the lounge."}

        path_to_lounge, _ = transporter.pathfinder.dijkstra(transporter.current_location, "Transporter Lounge")
        if not path_to_lounge:
            return {"error": f"No valid path to Transporter Lounge for {transporter_name}"}, 400

        transporter.move_to("Transporter Lounge")
        return {"status": f"{transporter_name} has returned to the lounge."}

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        return TransportationRequest.create(origin, destination, transport_type, urgent)

    def remove_transport_request(self, request_key):
        TransportationRequest.remove_completed_request(request_key)
        return {"status": f"Request {request_key} removed."}

    def get_transport_requests(self):
        return TransportationRequest.get_requests()

    def set_simulation_state(self, running: bool):
        self.simulation_running = running

    def get_all_requests(self):
        return (
            TransportationRequest.pending_requests +
            TransportationRequest.ongoing_requests +
            TransportationRequest.completed_requests
        )


