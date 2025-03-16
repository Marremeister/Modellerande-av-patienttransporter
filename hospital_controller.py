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
        self.pending_requests = []  # Stores requests waiting for assignment
        self.ongoing_requests = []  # Stores currently executing requests
        self.completed_requests = []  # Stores completed requests
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
        self.app.add_url_rule("/set_transporter_status", "set_transporter_status", self.set_transporter_status,
                              methods=["POST"])

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

    def get_request_by_status(self, status):
        """Returns requests filtered by status."""
        if status == "pending":
            return self.pending_requests
        elif status == "ongoing":
            return self.ongoing_requests
        elif status == "completed":
            return self.completed_requests
        return []

    def move_request_to_ongoing(self, request_obj):
        """Moves a request from pending to ongoing."""
        if request_obj in self.pending_requests:
            self.pending_requests.remove(request_obj)
            self.ongoing_requests.append(request_obj)
            request_obj.mark_as_ongoing()

    def mark_request_completed(self, request_obj):
        """Marks an ongoing request as completed and moves it to completed_requests."""
        if request_obj in self.ongoing_requests:
            self.ongoing_requests.remove(request_obj)
            self.completed_requests.append(request_obj)
            request_obj.mark_as_completed()

    def deploy_optimization(self):
        """Runs ILP optimization and assigns transporters in parallel."""
        optimizer = ILPOptimizer(self.transporters, self.pending_requests, self.model.get_graph())
        optimal_assignments = optimizer.optimize_transport_schedule()

        if not optimal_assignments:
            return jsonify({"error": "No valid assignments found"}), 400

        for t_name, origin, destination in optimal_assignments:
            transporter = next(t for t in self.transporters if t.name == t_name)
            request_obj = next(r for r in self.pending_requests if r.origin == origin and r.destination == destination)

            print(f"🚀 Deploying {transporter.name} for transport from {origin} to {destination}")

            self.socketio.emit("transporter_update",
                               {"name": transporter.name, "location": transporter.current_location})

            eventlet.spawn_n(self.assign_transport, transporter, request_obj)

        return jsonify({"status": "Optimization deployed, transporters are moving simultaneously!"})

    def get_hospital_graph(self):
        """Returns the hospital layout with standardized coordinates in JSON format."""
        return jsonify(self.model.get_graph().get_hospital_graph())

    def get_transporters(self):
        """Returns a list of available transporters with their current locations."""
        return jsonify([{
            "name": t.name,
            "current_location": t.current_location,
            "status": t.status  # 🔹 Ensure status is sent
        } for t in self.transporters])

    def get_transport_requests(self):
        """Returns categorized transport requests (pending, ongoing, completed)."""
        return jsonify({
            "pending": [
                {"origin": r.origin, "destination": r.destination, "transport_type": r.transport_type,
                 "urgent": r.urgent}
                for r in self.pending_requests
            ],
            "ongoing": [
                {"origin": r.origin, "destination": r.destination, "transport_type": r.transport_type,
                 "urgent": r.urgent}
                for r in self.ongoing_requests
            ],
            "completed": [
                {"origin": r.origin, "destination": r.destination, "transport_type": r.transport_type,
                 "urgent": r.urgent}
                for r in self.completed_requests
            ]
        })

    def set_transporter_status(self):
        """Allows toggling a transporter's active/inactive status via frontend."""
        data = request.get_json()
        transporter_name = data.get("transporter")
        status = data.get("status")

        transporter, error_response, status_code = self.get_transporter(transporter_name)
        if error_response:
            return error_response, status_code

        if status == "active":
            transporter.set_active()
        elif status == "inactive":
            transporter.set_inactive()
        else:
            return jsonify({"error": "Invalid status. Use 'active' or 'inactive'."}), 400

        return jsonify({"status": f"{transporter.name} is now {status}."})

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

    def process_transport(self, transporter, request_obj):
        """Handles the actual movement of the transporter along the path."""
        graph = self.model.get_graph()

        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request_obj.origin)
        path_to_destination, _ = transporter.pathfinder.dijkstra(request_obj.origin, request_obj.destination)

        full_path = list(path_to_origin[:-1]) + list(path_to_destination)  # Ensure path uniqueness

        if not full_path:
            print(f"❌ No valid path found for {transporter.name}. Aborting transport.")
            return

        print(f"🚛 {transporter.name} moving along: {full_path}")

        transporter.lock = getattr(transporter, "lock", eventlet.semaphore.Semaphore())

        for i in range(len(full_path) - 1):
            current_node = full_path[i]
            next_node = full_path[i + 1]

            travel_time = graph.get_edge_weight(current_node, next_node)

            with transporter.lock:
                transporter.current_location = next_node

            self.socketio.emit("transporter_update", {"name": transporter.name, "location": next_node})
            print(f"📍 {transporter.name} moved to {next_node}, travel time: {travel_time}s")

            eventlet.sleep(travel_time)  # Simulate movement time

        # ✅ Move request from ongoing to completed
        if request_obj in self.ongoing_requests:
            self.ongoing_requests.remove(request_obj)
            self.completed_requests.append(request_obj)
            print(f"✅ Transport request {request_obj.origin} ➝ {request_obj.destination} completed and archived.")

        # 🔥 Notify frontend that transport is completed
        self.socketio.emit("transport_completed", {"transporter": transporter.name})

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

        request_obj = next((r for r in self.pending_requests if r.origin == origin and r.destination == destination),
                           None)
        if not request_obj:
            return jsonify({"error": "Transport request not found with given origin and destination."}), 400

        return self.assign_transport(transporter, request_obj)

    def assign_transport(self, transporter, request_obj):
        """Assigns a transport request to a transporter and moves them step-by-step."""
        if transporter.status == "inactive":
            return jsonify({"error": f"❌ {transporter.name} is currently inactive and cannot be assigned a task."}), 400

        graph = self.model.get_graph()

        path_to_origin, _ = transporter.pathfinder.dijkstra(transporter.current_location, request_obj.origin)
        path_to_destination, _ = transporter.pathfinder.dijkstra(request_obj.origin, request_obj.destination)

        full_path = list(path_to_origin[:-1]) + list(path_to_destination)

        if not full_path:
            return jsonify({"error": "No valid path found"}), 400

        print(f"🚑 {transporter.name} assigned transport: {request_obj.origin} ➝ {request_obj.destination}")

        # 🔥 Mark request as ongoing
        request_obj.status = "ongoing"

        self.socketio.emit("transport_assigned", {
            "transporter": transporter.name,
            "origin": request_obj.origin,
            "destination": request_obj.destination,
            "transport_type": request_obj.transport_type,
            "urgent": request_obj.urgent
        })

        transporter.move_to(request_obj.origin)
        transporter.move_to(request_obj.destination)

        # ✅ Move request to completed list
        self.completed_requests.append(request_obj)
        self.pending_requests.remove(request_obj)

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
        self.transporters.append(
            PatientTransporter(self.model, name, self.socketio, start_location="Transporter Lounge"))

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
        """Removes a transport request after completion."""
        data = request.get_json()
        request_key = data.get("requestKey")

        self.completed_requests = [r for r in self.completed_requests if f"{r.origin}-{r.destination}" != request_key]

        return jsonify({"status": f"Request {request_key} removed."})

    def create_transport_request(self, origin, destination, transport_type="stretcher", urgent=False):
        """Creates a transport request manually (backend usage) or via API."""
        request_obj = TransportationRequest(request_time=None, origin=origin, destination=destination,
                                            transport_type=transport_type, urgent=urgent)
        self.pending_requests.append(request_obj)

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
