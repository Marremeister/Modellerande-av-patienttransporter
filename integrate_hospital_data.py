# integrate_hospital_data.py
"""
Script to integrate the real hospital data into the existing system.

Usage:
    python integrate_hospital_data.py <path_to_excel_file> [analysis_output_dir]
"""
import sys
import logging
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("IntegrationScript")


def integrate_real_hospital_data(excel_file, output_dir='analysis_output'):
    """
    Analyze hospital transport data and integrate it with the existing system.

    Args:
        excel_file: Path to Excel file with transport data
        output_dir: Directory to save analysis results

    Returns:
        bool: True if integration was successful
    """
    # Import required modules
    try:
        from Model.data_processor import TransportDataAnalyzer, HospitalGraphBuilder, CoordinateGenerator
        from Model.data_processor.integrate_with_system import SystemIntegrator
        from run_data_processor import analyze_data
        from Controller.hospital_controller import HospitalController
    except ImportError as e:
        logger.error(f"Error importing required modules: {str(e)}")
        logger.error("Make sure you're running this script from the project root directory.")
        return False

    # Check if Excel file exists
    if not os.path.exists(excel_file):
        logger.error(f"Excel file {excel_file} not found.")
        return False

    try:
        # Step 1: Analyze the data
        logger.info(f"Analyzing transport data from {excel_file}...")
        hospital, analyzer, _ = analyze_data(excel_file, output_dir)

        if not hospital or not analyzer:
            logger.error("Data analysis failed.")
            return False

        # Step 2: Create a temporary HospitalSystem
        import eventlet
        from flask_socketio import SocketIO

        # Create a mock SocketIO to avoid dependency issues
        class MockSocketIO:
            def emit(self, event, data=None, **kwargs):
                pass

        # Create a controller with the mock SocketIO
        socketio = MockSocketIO()
        controller = HospitalController(socketio)

        # Step 3: Integrate with the existing system
        logger.info("Integrating with existing hospital system...")
        integrator = SystemIntegrator(controller.system)

        # Replace the graph
        if not integrator.integrate_graph(hospital):
            logger.error("Failed to integrate graph with system.")
            return False

        # Update request generation patterns
        if not integrator.integrate_request_generation(analyzer):
            logger.error("Failed to update request generation patterns.")
            # Continue anyway, as this is not critical

        logger.info("Integration completed successfully.")

        # Show summary
        summarize_integration(controller.system, excel_file)

        return True

    except Exception as e:
        logger.error(f"Error during integration: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def summarize_integration(system, data_source):
    """Print a summary of the integrated system."""
    try:
        nodes = system.hospital.graph.get_nodes()
        edges_count = sum(len(edges) for node, edges in system.hospital.graph.adjacency_list.items()) // 2

        print("\n" + "=" * 60)
        print(f" HOSPITAL SYSTEM INTEGRATION SUMMARY ")
        print("=" * 60)
        print(f"Data Source: {data_source}")
        print(f"Graph Size: {len(nodes)} nodes, {edges_count} edges")
        print(f"Departments: {', '.join(sorted(nodes)[:10])}... (and {len(nodes) - 10} more)")
        print("\nTransport System:")
        print(f"  Active Transporters: {len(system.transport_manager.transporters)}")
        print(f"  Assignment Strategy: {system.transport_manager.assignment_strategy.__class__.__name__}")
        print("\nTo start using the integrated system:")
        print("  1. Restart your Flask application")
        print("  2. Navigate to the simulator page")
        print("  3. The real hospital graph is now being used for simulations")
        print("=" * 60)
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")


def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python integrate_hospital_data.py <path_to_excel_file> [output_directory]")
        return 1

    excel_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'analysis_output'

    # Run integration
    success = integrate_real_hospital_data(excel_file, output_dir)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())