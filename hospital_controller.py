import eventlet
eventlet.monkey_patch()
import eventlet.wsgi
from flask import Flask, render_template, request, jsonify, has_request_context
from flask_socketio import SocketIO
from hospital_model import Hospital
from model_patient_transporters import PatientTransporter
from model_transportation_request import TransportationRequest
from ilp_optimizer import ILPOptimizer
from eventlet.semaphore import Semaphore

# 🔒 Lock to prevent transporters from modifying shared data at the same time
transport_lock = Semaphore()


class HospitalController:
    def __init__(self):
        """Initialize hospital model, transporters, and viewer."""
        self.model = Hospital()
        self.transporters = []
        self.transport_requests = []
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, async_mode="eventlet", cors_allowed_origins="*")

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

    def index(self):
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
        """Runs ILP optimization and executes transport assignments in parallel."""
        optimizer = ILPOptimizer(self.transporters, self.transport_requests, self.model.get_graph())
        optimal_assignments = optimizer.optimize_transport_schedule()

        if not optimal_assignments:
            return jsonify({"error": "No valid assignments found"}), 400

        for t_name, origin, destination in optimal_assignments:
            transporter = next(t for t in self.transporters if t.name == t_name)
            request_obj = next(
                r for r in self.transport_requests if r.origin == origin and r.destination == destination)

            print(f"🚀 Deploying {transporter.name} for transport from {origin} to {destination}")

            # ✅ Emit initial position **before** moving
            self.socketio.emit("transporter_update",
                               {"name": transporter.name, "location": transporter.current_location})

            # 🔥 Run transport assignments in parallel
            eventlet.spawn_n(self.assign_transport, transporter, request_obj)

        return jsonify({"status": "Optimization deployed, transporters are moving simultaneously!"})

    def get_hospital_graph(self):
        """Returns the hospital layout with standardized coordinates in JSON format."""
        return jsonify(self.model.get_graph().get_hospital_graph())

    def get_transporters(self):
        """Returns a list of available transporters with their current locations."""
        return jsonify([{"name": t.name, "current_location": t.current_location} for t in self.transporters])

    def get_transport_requests(self):
        """Returns a list of available transport requests."""
        return jsonify([
            {"origin": r.origin, "destination": r.destination, "transport_type": r.transport_type, "urgent": r.urgent}
            for r in self.transport_requests
        ])

    def get_transporter(self, transporter_name):
        """Finds a transporter by name."""
        transporter = next((t for t in self.transporters if t.name == transporter_name), None)
        if not transporter:
            return None, jsonify({"error": "Transporter not found"}), 404
        return transporter, None, None

    def calculate_path(self, start, end, transporter):
        """Calculates the shortest path between two points."""
        path, _ = transporter.pathfinder.dijkstra(start, end)
        if not path:
            return None, jsonify({"error": f"No valid path from {start} to {end}"}), 400
        return path, None, None

    def move_transporter(self, transporter, path):
        """Moves transporter step by step, considering edge weights for travel time."""
        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]

            travel_time = self.get_travel_time(current_node, next_node)  # 🔹 Använder hjälpmetod

            transporter.current_location = next_node
            self.socketio.emit("transporter_update", {"name": transporter.name, "location": next_node})

            print(f"📍 {transporter.name} moving from {current_node} to {next_node}, will take {travel_time} seconds")
            eventlet.sleep(travel_time)  # ⏳ Fördröjning baserat på vikt

    def return_home(self):
        """Returns a transporter to the lounge when the button is clicked."""
        data = request.get_json()
        transporter_name = data.get("transporter")

        if not transporter_name:
            return jsonify({"error": "No transporter specified"}), 400

        transporter, error_response, status_code = self.get_transporter(transporter_name)
        if error_response:
            return error_response, status_code

        path_to_lounge, error_response, status_code = self.calculate_path(transporter.current_location, "Transporter Lounge", transporter)
        if error_response:
            return error_response, status_code

        self.move_transporter(transporter, path_to_lounge)
        return jsonify({"status": f"{transporter.name} has returned to the lounge."})

    def handle_assign_transport(self):
        """Handles the frontend request and extracts transporter and request objects."""
        data = request.get_json()
        print("📥 Received JSON payload:", data)  # Log input request

        transporter_name = data.get("transporter")
        origin = data.get("origin")
        destination = data.get("destination")

        if not transporter_name or not origin or not destination:
            return jsonify({"error": "Missing transporter, origin, or destination"}), 400

        transporter, error_response, status_code = self.get_transporter(transporter_name)
        if error_response:
            return error_response, status_code

        request_obj = next((r for r in self.transport_requests if r.origin == origin and r.destination == destination), None)
        if not request_obj:
            return jsonify({"error": "Transport request not found with given origin and destination."}), 400

        return self.assign_transport(transporter, request_obj)

    def assign_transport(self, transporter, request_obj):
        """Assigns a transport request to a transporter, moving step-by-step with weight-based timing."""
        graph = self.model.get_graph()

        # 🚀 Get unique paths for this transporter
        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request_obj.origin)
        path_to_destination, _ = transporter.pathfinder.dijkstra(request_obj.origin, request_obj.destination)

        full_path = list(path_to_origin[:-1]) + list(path_to_destination)  # Ensure each transporter has its own path

        if not full_path:
            return jsonify({"error": "No valid path found"}), 400

        print(f"🚑 {transporter.name} assigned transport. Moving along: {full_path}")

        # 🔥 Ensure each transporter has its own lock
        transporter.lock = getattr(transporter, "lock", eventlet.semaphore.Semaphore())

        self.socketio.emit("transporter_update", {"name": transporter.name, "location": transporter.current_location})

        for i in range(len(full_path) - 1):
            current_node = full_path[i]
            next_node = full_path[i + 1]

            # 🕒 Get travel time based on edge weight
            travel_time = graph.get_edge_weight(current_node, next_node)

            # 🔒 Lock for this transporter only
            with transporter.lock:
                transporter.current_location = next_node

            self.socketio.emit("transporter_update", {"name": transporter.name, "location": next_node})
            print(f"📍 {transporter.name} moved to {next_node}, travel time: {travel_time}s")

            eventlet.sleep(travel_time)  # ⏳ Wait based on edge weight

        # ✅ Remove the transport request after it is completed
        if request_obj in self.transport_requests:
            self.transport_requests.remove(request_obj)
            print(f"✅ Transport request {request_obj.origin} ➝ {request_obj.destination} completed and removed.")

            # 🔥 Emit an event to tell the frontend that a transport is done
            self.socketio.emit("transport_completed", {"transporter": transporter.name})

        return jsonify({"status": f"Transport assigned to {transporter.name}!"})

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

    def add_transporter(self):
        """Lägger till en ny patienttransportör via frontend genom att anropa create_transporter()."""
        data = request.get_json()
        transporter_name = data.get("name")

        if not transporter_name:
            return jsonify({"error": "Transporter name is required"}), 400

        # Kontrollera om transportören redan finns
        if any(t.name == transporter_name for t in self.transporters):
            return jsonify({"error": "A transporter with this name already exists"}), 400

        # 🔥 Återanvänd befintlig metod för att skapa transportören
        self.create_transporter(transporter_name)

        print(f"🚑 New transporter added via frontend: {transporter_name}")

        # Uppdatera frontend i realtid
        self.socketio.emit("new_transporter", {"name": transporter_name, "current_location": "Transporter Lounge"})

        return jsonify({"status": f"Transporter {transporter_name} added successfully!"})

    def remove_transport_request(self):
        """Removes a transport request after completion."""
        data = request.get_json()
        request_key = data.get("requestKey")

        if not request_key:
            return jsonify({"error": "Request key is required"}), 400

        self.transport_requests = [r for r in self.transport_requests if f"{r.origin}-{r.destination}" != request_key]

        return jsonify({"status": f"Request {request_key} removed."})

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        """Creates a transport request manually (backend usage) or via API."""
        request_obj = TransportationRequest(request_time=None, origin=origin, destination=destination,
                                            transport_type=transport_type, urgent=urgent)
        self.transport_requests.append(request_obj)

        response_message = f"Request from {origin} to {destination} created!"

        # 🔹 If called inside an API request, use jsonify
        if has_request_context():
            return jsonify({"status": response_message})

    def frontend_transport_request(self):
        """Handles transport requests coming from the frontend by calling the existing method."""
        data = request.get_json()
        origin = data.get("origin")
        destination = data.get("destination")
        transport_type = data.get("transport_type", "stretcher")
        urgent = data.get("urgent", False)

        if not origin or not destination:
            return jsonify({"error": "Origin and destination are required"}), 400

        # 🔹 Call the existing method
        return self.create_transport_request(origin, destination, transport_type, urgent)

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
        eventlet.wsgi.server(eventlet.listen(("127.0.0.1", 5001)), self.app)


if __name__ == "__main__":
    controller = HospitalController()
    controller.run()
