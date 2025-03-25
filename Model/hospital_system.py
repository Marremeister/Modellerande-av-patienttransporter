import eventlet
from Model.hospital_model import Hospital
from Model.model_transport_manager import TransportManager
from Model.model_patient_transporters import PatientTransporter
from Model.simulation import Simulation
from Model.Assignment_strategies.ILP.ilp_optimizer_strategy import ILPOptimizerStrategy
from Model.Assignment_strategies.Random.random_assignment_strategy import RandomAssignmentStrategy
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode
from Model.model_transportation_request import TransportationRequest
from Model.simulator_clock import SimulationClock



class HospitalSystem:
    def __init__(self, socketio, hospital=None):
        self.hospital = hospital or Hospital()
        self.socketio = socketio
        self.transport_manager = TransportManager(self.hospital, self.socketio)
        self.simulation = Simulation(self, socketio, interval=10)
        self.transport_manager.simulation = self.simulation
        self.clock = SimulationClock(speed_factor=10)
        self.clock.start()
        self.start_clock_emitter()

    def initialize(self):
        self._initialize_hospital()
        self._add_initial_data()

    # -----------------------------
    # 🔹 Setup
    # -----------------------------

    def _initialize_hospital(self):
        departments = [
            "Emergency", "ICU", "Surgery", "Radiology", "Reception",
            "Pediatrics", "Orthopedics", "Cardiology", "Neurology",
            "Pharmacy", "Laboratory", "General Ward", "Cafeteria", "Admin Office",
            "Transporter Lounge"
        ]

        corridors = [
            ("Emergency", "ICU", 5), ("ICU", "Surgery", 10),
            ("Surgery", "Radiology", 7), ("Emergency", "Reception", 3),
            ("Reception", "Pediatrics", 4), ("Pediatrics", "Orthopedics", 6),
            ("Orthopedics", "Cardiology", 8), ("Cardiology", "Neurology", 9),
            ("Neurology", "Pharmacy", 5), ("Pharmacy", "Laboratory", 4),
            ("Laboratory", "General Ward", 6), ("General Ward", "Cafeteria", 7),
            ("Cafeteria", "Admin Office", 5), ("Admin Office", "Reception", 6),
            ("Surgery", "General Ward", 8), ("Radiology", "Neurology", 7),
            ("Transporter Lounge", "Reception", 2)
        ]

        for dept in departments:
            self.hospital.add_department(dept)

        for d1, d2, dist in corridors:
            self.hospital.add_corridor(d1, d2, dist)

    def _add_initial_data(self):
        self.add_transporter("Anna")

        self.create_transport_request("Pediatrics", "Cafeteria", "stretcher", False)
        self.create_transport_request("Cafeteria", "Radiology", "stretcher", False)
        self.create_transport_request("Emergency", "ICU", "stretcher", True)
        self.create_transport_request("ICU", "Pediatrics", "stretcher", False)


    # -----------------------------
    # 🔹 Core Interface
    # -----------------------------
    def start_simulation(self):
        self.simulation.start()

    def stop_simulation(self):
        self.simulation.stop()

    def toggle_simulation(self, running: bool):
        if running:
            self.simulation.start()
            return {"status": "Simulation started"}, 200
        else:
            self.simulation.stop()
            return {"status": "Simulation stopped"}, 200

    def get_graph(self):
        return self.hospital.get_graph().get_hospital_graph()

    def add_transporter(self, name):
        if self.transport_manager.get_transporter(name):
            return self._error("A transporter with this name already exists")

        transporter = PatientTransporter(self.hospital, name, self.socketio)
        self.transport_manager.add_transporter(transporter)

        self.notify_transporter_added(transporter)

        return self._success(f"Transporter '{name}' added successfully")

    def notify_transporter_added(self, transporter):
        self.socketio.emit("new_transporter", {
            "name": transporter.name,
            "current_location": transporter.current_location
        })

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        return self.transport_manager.create_transport_request(origin, destination, transport_type, urgent)

    def frontend_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        request = self.create_transport_request(origin, destination, transport_type, urgent)

        self.log_event(
            f"📦 Transport request from {origin} to {destination} created. "
            f"Type: {transport_type}, Urgent: {urgent}"
        )

        return request

    def assign_transport(self, transporter_name, origin, destination):
        transporter = self.transport_manager.get_transporter(transporter_name)
        if not transporter:
            return self._error("Transporter not found")

        request_obj = next(
            (r for r in TransportationRequest.pending_requests
             if r.origin == origin and r.destination == destination),
            None
        )
        if not request_obj:
            return self._error("Transport request not found")

        # ✅ Backend log BEFORE assignment
        self.log_event(f"🛫 Assigning {transporter_name} to transport from {origin} to {destination}")

        result = self.transport_manager.assign_transport(transporter_name, request_obj)

        # ✅ Backend log AFTER assignment
        self.log_event(f"✅ {transporter_name} started transport from {origin} to {destination}")

        return self._success(result)

    def start_clock_emitter(self):
        def emit_loop():
            while True:
                sim_time = self.clock.get_time()
                self.socketio.emit("clock_tick", {"simTime": sim_time})
                eventlet.sleep(0.1)  # send every real second (adjust as needed)


        eventlet.spawn_n(emit_loop)

    def return_home(self, name):
        result = self.transport_manager.return_home(name)

        # Only log success (you could check result content more deeply if needed)
        if "error" not in result:
            self.log_event(f"🏠 {name} has returned to the Transporter Lounge.")

        return self._success(result)

    def deploy_strategy_assignment(self):
        response = self.transport_manager.deploy_strategy_assignment()
        if "error" in response:
            return self._error(response["error"])
        return self._success(response)

    def get_transporters(self):
        return self.transport_manager.get_transporters()

    def get_transport_requests(self):
        return self.transport_manager.get_transport_requests()

    def set_transporter_status(self, name, status):
        result = self.transport_manager.set_transporter_status(name, status)

        if "error" not in result:
            self.log_event(f"🔄 Status for {name} set to {status.upper()}.")

        return self._success(result)

    def remove_transport_request(self, request_key):
        return self._success(self.transport_manager.remove_transport_request(request_key))

    def log_event(self, message):
        self.socketio.emit("transport_log", {"message": message})

    def enable_random_mode(self):
        self.transport_manager.set_strategy(RandomAssignmentStrategy())

    def enable_optimized_mode(self, mode: ILPMode = ILPMode.MAKESPAN):
        """Allows setting the ILP strategy dynamically."""
        self.transport_manager.set_strategy(ILPOptimizerStrategy(mode))

    def use_ilp_equal_workload(self):
        self.enable_optimized_mode(ILPMode.EQUAL_WORKLOAD)

    def use_ilp_urgency_first(self):
        self.enable_optimized_mode(ILPMode.URGENCY_FIRST)

    def use_ilp_makespan(self):
        self.enable_optimized_mode(ILPMode.MAKESPAN)

    def reset_transporters(self, count):
        self.transport_manager.transporters.clear()

        for i in range(count):
            name = f"Sim_Transporter_{i + 1}"
            self.add_transporter(name)

    # -----------------------------
    # 🔹 Helpers
    # -----------------------------

    def _success(self, data):
        return {"success": True, "data": data}, 200

    def _error(self, message):
        return {"success": False, "error": message}, 400
