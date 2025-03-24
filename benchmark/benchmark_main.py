from Controller.hospital_controller import HospitalController
from benchmark_controller import BenchmarkController

# ✅ Add MockSocketIO to disable emit during benchmarking
class MockSocketIO:
    def emit(self, *args, **kwargs):
        pass

# 🧪 Sample transport requests for benchmarking
benchmark_requests = [
    ("Emergency", "ICU"),
    ("Reception", "Radiology"),
    ("ICU", "General Ward"),
    ("Cardiology", "Surgery"),
    ("Pharmacy", "Neurology"),
    ("Pediatrics", "Orthopedics"),
    ("Admin Office", "Cafeteria"),
    ("Radiology", "Laboratory"),
    ("Emergency", "Surgery"),
    ("Reception", "Cardiology")
]

if __name__ == "__main__":
    mock_socketio = MockSocketIO()

    # ✅ Use mock socketio to disable real-time events
    controller = HospitalController(socketio=mock_socketio)
    controller.system.initialize()

    benchmark = BenchmarkController(controller.system)

    # 🧪 Benchmark scenarios with different transporter setups
    scenarios = {
        "1 Transporter": ["Alpha"],
        "2 Transporters": ["Alpha", "Beta"],
        "5 Transporters": ["A", "B", "C", "D", "E"],
        "10 Transporters": [f"T{i}" for i in range(10)]
    }

    for label, transporters in scenarios.items():
        benchmark.run_and_plot(label, transporters, benchmark_requests)
