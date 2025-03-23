from flask import request, jsonify, render_template
from flask_socketio import SocketIO



class HospitalTransportViewer:
    def __init__(self, app, socketio: SocketIO, hospital_system):
        self.app = app
        self.socketio = socketio
        self.system = hospital_system  # 🧠 injected by HospitalController
        self._register_routes()

    def _register_routes(self):
        self.app.add_url_rule("/", "index", self.index)

        self.app.add_url_rule("/add_transporter", "add_transporter", self.add_transporter, methods=["POST"])
        self.app.add_url_rule("/get_hospital_graph", "get_graph", self.get_graph)
        self.app.add_url_rule("/get_transporters", "get_transporters", self.get_transporters)
        self.app.add_url_rule("/get_transport_requests", "get_transport_requests", self.get_transport_requests)

        self.app.add_url_rule("/return_home", "return_home", self.return_home, methods=["POST"])
        self.app.add_url_rule("/assign_transport", "assign_transport", self.assign_transport, methods=["POST"])

        self.app.add_url_rule("/frontend_transport_request", "frontend_transport_request",
                              self.frontend_transport_request, methods=["POST"])
        self.app.add_url_rule("/set_transporter_status", "set_transporter_status", self.set_transporter_status,
                              methods=["POST"])
        self.app.add_url_rule("/remove_transport_request", "remove_transport_request", self.remove_transport_request,
                              methods=["POST"])
        self.app.add_url_rule("/toggle_simulation", "toggle_simulation", self.toggle_simulation, methods=["POST"])

        # 🆕 Strategy switching
        self.app.add_url_rule("/deploy_strategy_assignment", "deploy_strategy_assignment",
                              self.deploy_strategy_assignment, methods=["POST"])
        self.app.add_url_rule("/use_random_assignment", "use_random_assignment",
                              self.use_random_assignment, methods=["POST"])
        self.app.add_url_rule("/use_ilp_assignment", "use_ilp_assignment",
                              self.use_ilp_assignment, methods=["POST"])

    # 👇 Views / Endpoints

    def index(self):
        return render_template("index.html")

    def add_transporter(self):
        data = request.get_json()
        name = data.get("name")
        if not name:
            return jsonify({"error": "Transporter name required"}), 400

        result, status = self.system.add_transporter(name)
        return jsonify(result), status

    def get_graph(self):
        return jsonify(self.system.get_graph())

    def get_transporters(self):
        return jsonify(self.system.get_transporters())

    def get_transport_requests(self):
        return jsonify(self.system.get_transport_requests())

    def return_home(self):
        data = request.get_json()
        return jsonify(self.system.return_home(data.get("transporter")))

    def assign_transport(self):
        data = request.get_json()
        return jsonify(*self.system.assign_transport(
            data.get("transporter"), data.get("origin"), data.get("destination")
        ))

    def frontend_transport_request(self):
        data = request.get_json()
        origin = data.get("origin")
        destination = data.get("destination")
        transport_type = data.get("transport_type", "stretcher")
        urgent = data.get("urgent", False)

        request_obj = self.system.frontend_transport_request(origin, destination, transport_type, urgent)
        return jsonify({
            "status": "Request created",
            "request": vars(request_obj)
        })

    def set_transporter_status(self):
        data = request.get_json()
        return jsonify(self.system.set_transporter_status(data.get("transporter"), data.get("status")))

    def remove_transport_request(self):
        data = request.get_json()
        return jsonify(self.system.remove_transport_request(data.get("requestKey")))

    def toggle_simulation(self):
        data = request.get_json()
        running = data.get("running", False)

        self.system.transport_manager.set_simulation_state(running)

        if running:
            self.system.simulation.start()
        else:
            self.system.simulation.stop()

        return jsonify({"status": "Simulation started" if running else "Simulation stopped"})

    # 🧠 Assignment strategy switching
    def deploy_strategy_assignment(self):
        return jsonify(self.system.deploy_strategy_assignment())

    def use_random_assignment(self):
        self.system.enable_random_mode()
        return jsonify({"status": "✅ Switched to Random Assignment"})

    def use_ilp_assignment(self):
        self.system.enable_optimized_mode()
        return jsonify({"status": "✅ Switched to ILP Optimizer"})
