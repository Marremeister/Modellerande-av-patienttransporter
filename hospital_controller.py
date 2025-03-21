import eventlet
eventlet.monkey_patch()
import eventlet.wsgi
from flask import Flask, render_template, request, jsonify, has_request_context
from flask_socketio import SocketIO
from hospital_model import Hospital
from model_patient_transporters import PatientTransporter
from eventlet.semaphore import Semaphore
from model_transport_manager import TransportManager


# 🔒 Lock to prevent transporters from modifying shared data at the same time
transport_lock = Semaphore()


class HospitalController:
    def __init__(self):
        """Initialize hospital model, transporters, and viewer."""
        self.model = Hospital()
        self.transporters = []
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, async_mode="eventlet", cors_allowed_origins="*")
        self.transport_manager = TransportManager(self.model, self.socketio)
        # Define API routes
        self.app.add_url_rule("/frontend_transport_request", "frontend_transport_request",
                              self.frontend_transport_request, methods=["POST"])
        self.app.add_url_rule("/remove_transport_request", "remove_transport_request", self.remove_transport_request,
                              methods=["POST"])
        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/get_hospital_graph", "get_hospital_graph", self.get_hospital_graph, methods=["GET"])
        self.app.add_url_rule("/assign_transport", "assign_transport", self.handle_assign_transport, methods=["POST"])
        self.app.add_url_rule("/return_home", "return_home", self.return_home, methods=["POST"])
        self.app.add_url_rule("/get_transporters", "get_transporters", self.get_transporters, methods=["GET"])
        self.app.add_url_rule("/get_transport_requests", "get_transport_requests", self.get_transport_requests, methods=["GET"])
        self.app.add_url_rule("/deploy_optimization", "deploy_optimization", self.deploy_optimization, methods=["POST"])
        self.app.add_url_rule("/add_transporter", "add_transporter", self.add_transporter, methods=["POST"])
        self.app.add_url_rule("/set_transporter_status", "set_transporter_status", self.set_transporter_status,
                              methods=["POST"])

    @staticmethod
    def index():
        """Serves the frontend page."""
        return render_template("index.html")

    def get_travel_time(self, node1, node2):
        """Returns the travel time based on the weight of the edge between two nodes."""
        graph = self.model.get_graph()
        weight = graph.get_edge_weight(node1, node2)

        if weight is None:
            print(f"⚠️ Warning: No weight found for {node1} → {node2}, defaulting to 1s")
            weight = 1  # Standardvärde om ingen vikt finns

        return weight

    def deploy_optimization(self):
        """API endpoint to run optimization and assign transporters."""
        response = self.transport_manager.deploy_optimization()
        return jsonify(response), (400 if "error" in response else 200)

    def get_hospital_graph(self):
        """Returns the hospital layout with standardized coordinates in JSON format."""
        return jsonify(self.model.get_graph().get_hospital_graph())

    def get_transporters(self):
        """Returns a list of transporters from TransportManager."""
        return jsonify(self.transport_manager.get_transporters())

    def get_transport_requests(self):
        """Returns transport requests grouped by status."""
        return jsonify(self.transport_manager.get_transport_requests())  # ✅ FIXED: Use TransportManager

    def set_transporter_status(self):
        """Allows toggling a transporter's active/inactive status via frontend."""
        data = request.get_json()
        transporter_name = data.get("transporter")
        status = data.get("status")

        result = self.transport_manager.set_transporter_status(transporter_name, status)
        return jsonify(result)

    def get_transporter(self, transporter_name):
        """Finds a transporter by name."""
        transporter = next((t for t in self.transporters if t.name == transporter_name), None)
        if not transporter:
            return None, jsonify({"error": "Transporter not found"}), 404
        return transporter, None, None

    @staticmethod
    def calculate_path(start, end, transporter):
        """Calculates the shortest path between two points."""
        path, _ = transporter.pathfinder.dijkstra(start, end)
        if not path:
            return None, jsonify({"error": f"No valid path from {start} to {end}"}), 400
        return path, None, None

    def return_home(self):
        """Handles the frontend request to return a transporter to the lounge."""
        data = request.get_json()
        transporter_name = data.get("transporter")

        if not transporter_name:
            return jsonify({"error": "No transporter specified"}), 400

        return jsonify(self.transport_manager.return_home(transporter_name))

    def handle_assign_transport(self):
        """Handles the frontend request and extracts transporter and request objects."""
        data = request.get_json()
        print("📥 Received JSON payload:", data)  # Log input request

        transporter_name = data.get("transporter")
        origin = data.get("origin")
        destination = data.get("destination")

        if not transporter_name or not origin or not destination:
            return jsonify({"error": "Missing transporter, origin, or destination"}), 400

        transporter = self.transport_manager.get_transporter(transporter_name)
        if not transporter:
            return jsonify({"error": f"Transporter {transporter_name} not found"}), 400

        request_obj = next(
            (r for r in self.transport_manager.pending_requests if r.origin == origin and r.destination == destination),
            None)

        if not request_obj:
            return jsonify({"error": "Transport request not found with given origin and destination."}), 400

        return jsonify(self.transport_manager.assign_transport(transporter_name, request_obj))

    def initialize_hospital(self):
        """Initialize hospital departments and corridors."""
        departments = [
            "Emergency", "ICU", "Surgery", "Radiology", "Reception",
            "Pediatrics", "Orthopedics", "Cardiology", "Neurology",
            "Pharmacy", "Laboratory", "General Ward", "Cafeteria", "Admin Office",
            "Transporter Lounge"
        ]
        for dept in departments:
            self.model.add_department(dept)

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
        for dept1, dept2, distance in corridors:
            self.model.add_corridor(dept1, dept2, distance)

    def create_transporter(self, name):
        """Create and store a transporter."""
        self.transport_manager.add_transporter(PatientTransporter(self.model, name, self.socketio))

    def add_transporter(self):
        """Adds a new patient transporter via frontend."""
        data = request.get_json()
        transporter_name = data.get("name")

        if not transporter_name:
            return jsonify({"error": "Transporter name is required"}), 400

        # 🔥 Check if transporter already exists
        if any(t.name == transporter_name for t in self.transporters):
            return jsonify({"error": "A transporter with this name already exists"}), 400

        # 🔹 Pass `self.socketio` when creating transporter
        self.create_transporter(transporter_name)

        print(f"🚑 New transporter added via frontend: {transporter_name}")

        # 🔥 Update frontend in real-time
        self.socketio.emit("new_transporter", {"name": transporter_name, "current_location": "Transporter Lounge"})

        return jsonify({"status": f"Transporter {transporter_name} added successfully!"})

    def remove_transport_request(self):
        """Handles the frontend request to remove a completed transport request."""
        data = request.get_json()
        request_key = data.get("requestKey")

        return jsonify(self.transport_manager.remove_transport_request(request_key))

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        """Creates a transport request via TransportManager."""
        return jsonify(self.transport_manager.create_transport_request(origin, destination, transport_type, urgent))

    def frontend_transport_request(self):
        """Handles transport requests from the frontend."""
        data = request.get_json()
        print("📥 Received frontend transport request:", data)

        origin = data.get("origin")
        destination = data.get("destination")
        transport_type = data.get("transport_type", "stretcher")
        urgent = data.get("urgent", False)

        if not origin or not destination:
            return jsonify({"error": "Origin and destination are required"}), 400

        # 🔥 Delegate request creation to TransportManager
        request_obj = self.transport_manager.create_transport_request(origin, destination, transport_type, urgent)

        return jsonify({"status": f"Request from {origin} to {destination} created!", "request": vars(request_obj)})

    def run(self):
        """Run the system by initializing all components."""
        self.initialize_hospital()

        # 🔹 Now using TransportManager to create transporters
        self.transport_manager.add_transporter(PatientTransporter(self.model, "Anna", self.socketio))
        self.transport_manager.add_transporter(PatientTransporter(self.model, "Bob", self.socketio))

        print("🚑 Created transporters: Anna and Bob at Transporter Lounge")

        # 🔹 Now using TransportManager for transport requests
        self.transport_manager.create_transport_request("Emergency", "ICU", "stretcher", True)
        self.transport_manager.create_transport_request("Reception", "Radiology", "wheelchair", False)

        print("📦 Created transport requests: Emergency to ICU, Reception to Radiology")

        print("🚀 Hospital system running on http://127.0.0.1:5001")
        eventlet.wsgi.server(eventlet.listen(("127.0.0.1", 5001)), self.app)


if __name__ == "__main__":
    controller = HospitalController()
    controller.run()
