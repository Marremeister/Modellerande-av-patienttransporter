from flask import request, jsonify
from flask_socketio import SocketIO


class HospitalTransportViewer:
    def __init__(self, app):
        """Initialize WebSocket communication using Flask-SocketIO and attach it to an existing Flask app."""
        self.app = app
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.transporters = {}  # Dictionary to store transporter movements

        # Define routes within the existing Flask app
        self.app.add_url_rule("/update_transporter", "update_transporter", self.update_transporter, methods=["POST"])
        self.app.add_url_rule("/get_transporters", "get_transporters", self.get_transporters)

    def emit_transporter_update(self, name, path):
        """Send a transport update to the frontend."""
        print(f"📡 Emitting transporter update: {name} moving on {path}")
        self.socketio.emit("transporter_update", {"name": name, "path": path})

    def update_transporter(self):
        """Handles transporter updates from external requests."""
        data = request.json
        print(f"📥 Received transporter update request: {data}")
        name = data.get("name")
        path = data.get("path", [])
        if name and path:
            self.transporters[name] = path
            self.emit_transporter_update(name, path)
            return jsonify({"status": "updated"})
        return jsonify({"error": "Invalid data"}), 400

    def get_transporters(self):
        """Returns a JSON list of active transporters and their paths."""
        return jsonify(self.transporters)
