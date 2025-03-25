import eventlet
eventlet.monkey_patch()
from flask import Flask
from flask_socketio import SocketIO

from Controller.hospital_controller import HospitalController
from View.hospital_transport_viewer import HospitalTransportViewer
from new_backend_benchmark import setup_benchmark

# Initialize Flask and SocketIO
app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

# Initialize hospital system components
controller = HospitalController(socketio)
viewer = HospitalTransportViewer(app, socketio, controller.system)

# Setup benchmark functionality using the new MVC structure
benchmark_controller = setup_benchmark(app, socketio, controller.system)

if __name__ == "__main__":
    print("🚀 Hospital system running on http://127.0.0.1:5001")
    print("  - Main interface: http://127.0.0.1:5001/")
    print("  - Simulator: http://127.0.0.1:5001/simulator")
    print("  - Benchmark: http://127.0.0.1:5001/benchmark")
    socketio.run(app, host="127.0.0.1", port=5001, debug=True)