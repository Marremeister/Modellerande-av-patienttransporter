import eventlet
eventlet.monkey_patch()
import eventlet.wsgi
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from hospital_model import Hospital
from model_patient_transporters import PatientTransporter
from model_transportation_request import TransportationRequest
import time


class HospitalController:
    def __init__(self):
        """Initialize hospital model, transporters, and viewer."""
        self.model = Hospital()
        self.transporters = []
        self.transport_requests = []
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, async_mode="eventlet", cors_allowed_origins="*")

        # Define API routes
        self.app.add_url_rule("/return_home", "return_home", self.return_home, methods=["POST"])
        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/get_hospital_graph", "get_hospital_graph", self.get_hospital_graph, methods=["GET"])
        self.app.add_url_rule("/assign_transport", "assign_transport", self.handle_assign_transport, methods=["POST"])
        self.app.add_url_rule("/get_transporters", "get_transporters", self.get_transporters, methods=["GET"])
        self.app.add_url_rule("/get_transport_requests", "get_transport_requests", self.get_transport_requests,
                              methods=["GET"])

    def index(self):
        """Serves the frontend page."""
        return render_template("index.html")

    def return_home(self):
        """Returns a transporter to the lounge when the button is clicked."""
        data = request.get_json()
        transporter_name = data.get("transporter")

        if not transporter_name:
            return jsonify({"error": "No transporter specified"}), 400

        transporter = next((t for t in self.transporters if t.name == transporter_name), None)

        if not transporter:
            return jsonify({"error": "Transporter not found"}), 404

        # Hitta snabbaste vägen tillbaka till loungen
        path_to_lounge, _ = transporter.pathfinder.dijkstra(transporter.current_location, "Transporter Lounge")

        if not path_to_lounge:
            return jsonify({"error": "No valid path found"}), 400

        print(f"🚑 {transporter.name} returning home: {path_to_lounge}")

        # Flytta transportören steg för steg
        for node in path_to_lounge:
            transporter.current_location = node
            self.socketio.emit("transporter_update", {"name": transporter.name, "location": node})
            eventlet.sleep(1)  # Simulera fördröjning

        return jsonify({"status": f"{transporter.name} has returned to the lounge."})


    def get_hospital_graph(self):
        """Returns the hospital layout with standardized coordinates in JSON format."""
        return jsonify(self.model.get_graph().get_hospital_graph())

    def get_transporters(self):
        """Returns a list of available transporters with their current locations."""
        return jsonify([
            {"name": t.name, "current_location": t.current_location} for t in self.transporters
        ])

    def get_transport_requests(self):
        """Returns a list of available transport requests."""
        return jsonify(
            [{"origin": r.origin, "destination": r.destination, "transport_type": r.transport_type, "urgent": r.urgent}
             for r in self.transport_requests])

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
        self.transporters.append(PatientTransporter(self.model, name, start_location="Transporter Lounge"))

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        """Create a transportation request and store it with correct argument order."""
        request_obj = TransportationRequest(request_time=None, origin=origin, destination=destination,
                                            transport_type=transport_type, urgent=urgent)
        self.transport_requests.append(request_obj)

    def handle_assign_transport(self):
        """Handles the frontend request and extracts transporter and request objects."""
        data = request.get_json()
        print("📥 Received JSON payload:", data)  # Log input request

        transporter_name = data.get("transporter")
        origin = data.get("origin")
        destination = data.get("destination")

        if not transporter_name or not origin or not destination:
            print(
                f"⚠️ Missing required fields! Transporter: {transporter_name}, Origin: {origin}, Destination: {destination}")
            return jsonify({"error": "Missing transporter, origin, or destination"}), 400

        transporter = next((t for t in self.transporters if t.name == transporter_name), None)
        request_obj = next((r for r in self.transport_requests if r.origin == origin and r.destination == destination),
                           None)

        if not transporter:
            return jsonify({"error": "Transporter not found"}), 400

        if not request_obj:
            return jsonify({"error": "Transport request not found with given origin and destination."}), 400

        return self.assign_transport(transporter, request_obj)

    def assign_transport(self, transporter, request_obj):
        """Assigns a transport request to a transporter and updates its position step-by-step."""
        graph = self.model.get_graph()

        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request_obj.origin)
        path_to_destination, _ = transporter.pathfinder.dijkstra(request_obj.origin, request_obj.destination)
        #path_to_lounge, _ = transporter.pathfinder.dijkstra(request_obj.destination, "Transporter Lounge")

        #full_path = path_to_origin[:-1] + path_to_destination[:-1] + path_to_lounge
        full_path = path_to_origin[:-1] + path_to_destination

        if not full_path:
            return jsonify({"error": "No valid path found"}), 400

        print(f"🚑 {transporter.name} assigned transport. Moving along: {full_path}")

        # Emit start location
        self.socketio.emit("transporter_update", {"name": transporter.name, "location": transporter.current_location})

        # Move step by step
        for node in full_path:
            transporter.current_location = node
            self.socketio.emit("transporter_update", {"name": transporter.name, "location": node})
            print(f"📍 {transporter.name} moved to {node}")
            eventlet.sleep(1)  # Simulate transport delay

        return jsonify({"status": f"Transport assigned to {transporter.name}!"})

    def run(self):
        """Run the system by initializing all components and starting necessary processes."""
        self.initialize_hospital()
        self.create_transporter("Anna")
        self.create_transporter("Bob")
        print("🚑 Created transporters: Anna and Bob at Transporter Lounge")

        # Create sample transport requests
        self.create_transport_request("Emergency", "ICU", "stretcher", True)
        self.create_transport_request("Reception", "Radiology", "wheelchair", False)
        print("📦 Created transport requests: Emergency to ICU, Reception to Radiology")

        print("🚀 Hospital system running on http://127.0.0.1:5001")

        # Run with eventlet
        eventlet.wsgi.server(eventlet.listen(("127.0.0.1", 5001)), self.app)


if __name__ == "__main__":
    controller = HospitalController()
    controller.run()
