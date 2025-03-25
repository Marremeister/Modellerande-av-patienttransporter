from flask import request, jsonify, render_template
from flask_socketio import SocketIO

class HospitalTransportViewer:
    def __init__(self, app, socketio: SocketIO, hospital_system):
        self.app = app
        self.socketio = socketio
        self.system = hospital_system  # 🧠 injected by HospitalController
        self._register_routes()

    def _register_routes(self):
        # Pages
        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/simulator", "simulator", self.simulator_page)

        # Transport System
        self.app.add_url_rule("/add_transporter", "add_transporter", self.add_transporter, methods=["POST"])
        self.app.add_url_rule("/get_hospital_graph", "get_graph", self.get_graph)
        self.app.add_url_rule("/get_transporters", "get_transporters", self.get_transporters)
        self.app.add_url_rule("/get_transport_requests", "get_transport_requests", self.get_transport_requests)
        self.app.add_url_rule("/get_all_transports", "get_all_transports", self.get_all_transports)

        self.app.add_url_rule("/return_home", "return_home", self.return_home, methods=["POST"])
        self.app.add_url_rule("/assign_transport", "assign_transport", self.assign_transport, methods=["POST"])
        self.app.add_url_rule("/frontend_transport_request", "frontend_transport_request", self.frontend_transport_request, methods=["POST"])
        self.app.add_url_rule("/remove_transport_request", "remove_transport_request", self.remove_transport_request, methods=["POST"])

        self.app.add_url_rule("/set_transporter_status", "set_transporter_status", self.set_transporter_status, methods=["POST"])
        self.app.add_url_rule("/toggle_simulation", "toggle_simulation", self.toggle_simulation, methods=["POST"])

        # Strategy & Simulator Config
        self.app.add_url_rule("/deploy_strategy_assignment", "deploy_strategy_assignment", self.deploy_strategy_assignment, methods=["POST"])
        self.app.add_url_rule("/update_simulator_config", "update_simulator_config", self.update_simulator_config, methods=["POST"])
        self.app.add_url_rule("/set_strategy_by_name", "set_strategy_by_name", self.set_strategy_by_name, methods=["POST"])
        self.app.add_url_rule("/get_available_strategies", "get_available_strategies", self.get_available_strategies)

    # --- Pages ---

    def index(self):
        return render_template("index.html")

    def simulator_page(self):
        return render_template("simulator.html")

    # --- Config Endpoints ---

    def update_simulator_config(self):
        data = request.get_json()
        num_transporters = data.get("num_transporters")
        request_interval = data.get("request_interval")
        strategy = data.get("strategy")

        if num_transporters is not None:
            self.system.reset_transporters(num_transporters)

        if request_interval is not None:
            self.system.simulation.set_request_interval(request_interval)

        if strategy:
            self.system.transport_manager.set_strategy_by_name(strategy)

        return jsonify({"status": "✅ Simulator config updated."})

    def set_strategy_by_name(self):
        data = request.get_json()
        strategy = data.get("strategy")
        if not strategy:
            return jsonify({"error": "Strategy name is required"}), 400

        result = self.system.transport_manager.set_strategy_by_name(strategy)
        return jsonify(result)

    # --- Transporter Management ---

    def add_transporter(self):
        data = request.get_json()
        name = data.get("name")
        if not name:
            return jsonify({"error": "Transporter name required"}), 400

        result, status = self.system.add_transporter(name)
        return jsonify(result), status

    def set_transporter_status(self):
        data = request.get_json()
        return jsonify(self.system.set_transporter_status(data.get("transporter"), data.get("status")))

    def return_home(self):
        data = request.get_json()
        return jsonify(self.system.return_home(data.get("transporter")))

    # --- Transport Requests ---

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

    def remove_transport_request(self):
        data = request.get_json()
        return jsonify(self.system.remove_transport_request(data.get("requestKey")))

    # --- Info ---

    def get_graph(self):
        return jsonify(self.system.get_graph())

    def get_transporters(self):
        return jsonify(self.system.get_transporters())

    def get_transport_requests(self):
        return jsonify(self.system.get_transport_requests())

    def get_all_transports(self):
        all_transports = self.system.transport_manager.get_all_requests()

        def format_request(req):
            return {
                "origin": req.origin,
                "destination": req.destination,
                "transport_type": req.transport_type,
                "urgent": req.urgent,
                "assigned_transporter": req.get_transporter_name(),
                "status": req.status
            }

        return jsonify([format_request(r) for r in all_transports])

    # --- Simulation ---

    def toggle_simulation(self):
        data = request.get_json()
        running = data.get("running", False)

        self.system.transport_manager.set_simulation_state(running)

        if running:
            self.system.simulation.start()
        else:
            self.system.simulation.stop()

        return jsonify({"status": "Simulation started" if running else "Simulation stopped"})

    def deploy_strategy_assignment(self):
        return jsonify(self.system.deploy_strategy_assignment())

    def get_available_strategies(self):
        strategies = self.system.transport_manager.get_available_strategy_names()
        print(strategies)
        return jsonify(strategies)

