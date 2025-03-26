"""
Benchmark package for hospital transport system.
Provides tools to compare different transport assignment strategies.
"""

from .benchmark_model import BenchmarkModel
from .benchmark_controller import BenchmarkController
from .benchmark_view import BenchmarkView


def setup_benchmark(app, socketio, hospital_system):
    """
    Initialize and connect all benchmark components.

    Args:
        app: Flask application instance
        socketio: Flask-SocketIO instance
        hospital_system: Hospital system instance

    Returns:
        BenchmarkController: The initialized benchmark controller
    """
    # Create MVC components
    model = BenchmarkModel(hospital_system)
    controller = BenchmarkController(model, socketio)
    view = BenchmarkView(app, socketio, controller)

    # Register routes
    view.register_routes()

    print("✅ Benchmark MVC initialized")
    return controller

