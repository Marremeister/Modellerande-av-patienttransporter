from flask import Flask
from flask_socketio import SocketIO

from Controller.hospital_controller import HospitalController
from View.hospital_transport_viewer import HospitalTransportViewer

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

controller = HospitalController(socketio)
viewer = HospitalTransportViewer(app, socketio, controller.system)

if __name__ == "__main__":
    print("🚀 Hospital system running on http://127.0.0.1:5000")
    socketio.run(app, host="127.0.0.1", port=5001, debug=True)
