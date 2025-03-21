from flask import Flask
from flask_socketio import SocketIO
from hospital_system import HospitalSystem
from hospital_transport_viewer import HospitalTransportViewer
import eventlet
import eventlet.wsgi


class HospitalController:
    def __init__(self):
        # 🔧 Create the app and socket server
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, async_mode="eventlet", cors_allowed_origins="*")

        # 🧠 Create the system and initialize it
        self.system = HospitalSystem(self.socketio)
        self.system.initialize()

        # 👁️ Set up the viewer (routes and UI interaction)
        self.viewer = HospitalTransportViewer(self.app, self.socketio, self.system)

    def run(self):
        print("🚀 Hospital system running on http://127.0.0.1:5001")
        eventlet.wsgi.server(eventlet.listen(("127.0.0.1", 5001)), self.app)


if __name__ == "__main__":
    controller = HospitalController()
    controller.run()
