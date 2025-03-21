from hospital_model import Hospital
from model_transport_manager import TransportManager
from model_patient_transporters import PatientTransporter


class HospitalSystem:
    def __init__(self, socketio, hospital=None):
        self.hospital = hospital or Hospital()
        self.socketio = socketio
        self.transport_manager = TransportManager(self.hospital, self.socketio)

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
        self.add_transporter("Bob")

        self.create_transport_request("Emergency", "ICU", "stretcher", True)
        self.create_transport_request("Reception", "Radiology", "wheelchair", False)

    # -----------------------------
    # 🔹 Core Interface
    # -----------------------------

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

    def assign_transport(self, transporter_name, origin, destination):
        transporter = self.transport_manager.get_transporter(transporter_name)
        if not transporter:
            return self._error("Transporter not found")

        request_obj = next(
            (r for r in self.transport_manager.pending_requests
             if r.origin == origin and r.destination == destination),
            None
        )
        if not request_obj:
            return self._error("Transport request not found")

        return self._success(self.transport_manager.assign_transport(transporter_name, request_obj))

    def return_home(self, name):
        return self._success(self.transport_manager.return_home(name))

    def deploy_optimization(self):
        response = self.transport_manager.deploy_optimization()
        if "error" in response:
            return self._error(response["error"])
        return self._success(response)

    def get_transporters(self):
        return self.transport_manager.get_transporters()

    def get_transport_requests(self):
        return self.transport_manager.get_transport_requests()

    def set_transporter_status(self, name, status):
        return self._success(self.transport_manager.set_transporter_status(name, status))

    def remove_transport_request(self, request_key):
        return self._success(self.transport_manager.remove_transport_request(request_key))

    # -----------------------------
    # 🔹 Helpers
    # -----------------------------

    def _success(self, data):
        return {"success": True, "data": data}, 200

    def _error(self, message):
        return {"success": False, "error": message}, 400
