# Model/data_processor/integrate_with_system.py
"""
Module to integrate the data-derived hospital graph with the existing hospital system.
"""
import logging
import os
from Model.hospital_model import Hospital


class SystemIntegrator:
    """
    Integrates a data-derived hospital graph with the existing hospital system.
    """

    def __init__(self, hospital_system):
        """
        Initialize the integrator with a reference to the hospital system.

        Args:
            hospital_system: The existing HospitalSystem instance
        """
        self.hospital_system = hospital_system
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a logger for the SystemIntegrator."""
        logger = logging.getLogger("SystemIntegrator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def integrate_graph(self, new_hospital):
        """
        Replace the graph in the existing hospital system with the data-derived one.

        Args:
            new_hospital: Hospital instance with data-derived graph

        Returns:
            bool: True if integration succeeded
        """
        if not new_hospital or not new_hospital.graph:
            self.logger.error("Invalid new hospital or hospital graph.")
            return False

        try:
            self.logger.info("Starting graph integration...")

            # Store a reference to the original graph
            original_graph = self.hospital_system.hospital.graph

            # Replace the graph in the hospital
            self.hospital_system.hospital.graph = new_hospital.graph

            # Update departments list
            self.hospital_system.hospital.departments = new_hospital.graph.get_nodes()

            self.logger.info("Graph integration complete.")
            return True
        except Exception as e:
            self.logger.error(f"Error during graph integration: {str(e)}")
            # Rollback if possible
            if hasattr(self, 'original_graph'):
                self.hospital_system.hospital.graph = original_graph
            return False

    def integrate_request_generation(self, analyzer, simulation=None):
        """
        Update the simulation's request generation based on real data patterns.

        Args:
            analyzer: TransportDataAnalyzer with processed data
            simulation: Optional Simulation instance (defaults to hospital_system.simulation)

        Returns:
            bool: True if integration succeeded
        """
        if simulation is None:
            simulation = self.hospital_system.simulation

        if not simulation:
            self.logger.error("No simulation instance available.")
            return False

        if not analyzer:
            self.logger.error("No analyzer provided.")
            return False

        try:
            self.logger.info("Updating request generation patterns...")

            # Store origin-destination frequencies
            od_pairs = analyzer.get_origin_destination_pairs()

            # Calculate median transport times (for difficulty estimation)
            median_times = analyzer.get_median_transport_times()

            # Get hourly distribution
            hourly_dist = analyzer.get_hourly_request_distribution()

            # Create frequency-based selection function
            def get_weighted_od_pair():
                """Randomly select an origin-destination pair based on frequency."""
                import random
                return random.choice(od_pairs)  # Replace with weighted selection

            # Create time-based rate function
            def get_request_rate(hour):
                """Get request rate for a specific hour."""
                if hour in hourly_dist:
                    return hourly_dist[hour]
                return max(1, sum(hourly_dist.values()) // 24)  # fallback to average

            # Attach to simulation
            simulation.get_weighted_od_pair = get_weighted_od_pair
            simulation.get_request_rate = get_request_rate

            # Store reference to original _run_loop to allow monkey patching
            original_run_loop = simulation._run_loop

            # Define a new _run_loop that uses our data patterns
            def data_driven_run_loop(self):
                """Main simulation loop with data-driven request generation."""
                import random
                import eventlet
                import datetime

                graph = self.system.hospital.get_graph()
                locations = list(graph.get_nodes())

                while self.running:
                    # Get current hour from clock
                    current_hour = datetime.datetime.now().hour

                    # Adjust rate based on hour
                    rate = self.get_request_rate(current_hour)
                    adjusted_interval = max(1, self.interval * (10 / rate))  # Scale by rate

                    # Get origin-destination
                    origin, destination = self.get_weighted_od_pair()

                    # Randomly choose transport type and urgency
                    transport_type = random.choice(["stretcher", "wheelchair", "bed"])
                    urgent = random.choice([True, False, False, False])  # 25% chance of urgent

                    # Create request
                    request = self.system.create_transport_request(origin, destination, transport_type, urgent)

                    self.socketio.emit("simulation_event", {
                        "type": "new_request",
                        "origin": origin,
                        "destination": destination,
                        "transport_type": transport_type,
                        "urgent": urgent
                    })

                    self.system.log_event(
                        f"🆕 New request created: {origin} ➝ {destination} ({transport_type}, urgent={urgent})"
                    )

                    # Deploy optimization
                    self.system.transport_manager.deploy_strategy_assignment()

                    # Wait before next request
                    eventlet.sleep(adjusted_interval)

            # Monkey patch the simulation._run_loop method
            simulation._run_loop = lambda: data_driven_run_loop(simulation)

            self.logger.info("Request generation patterns updated.")
            return True
        except Exception as e:
            self.logger.error(f"Error updating request generation: {str(e)}")
            return False

    def load_analyzed_data(self, analysis_dir='analysis_output'):
        """
        Load analyzed data and initialize components for integration.

        Args:
            analysis_dir: Directory with analysis results

        Returns:
            tuple: (new_hospital, analyzer) for further integration
        """
        try:
            from Model.Data_processor import TransportDataAnalyzer
            from Model.hospital_model import Hospital
            import pandas as pd
            import json

            # Check if analysis directory exists
            if not os.path.exists(analysis_dir):
                self.logger.error(f"Analysis directory {analysis_dir} not found.")
                return None, None

            # Create a new Hospital instance
            new_hospital = Hospital()

            # Load node coordinates
            coord_file = os.path.join(analysis_dir, 'node_coordinates.json')
            if os.path.exists(coord_file):
                with open(coord_file, 'r') as f:
                    coordinates = json.load(f)

                # Add nodes with coordinates
                for node, (x, y) in coordinates.items():
                    new_hospital.add_department(node)
                    new_hospital.graph.set_node_coordinates(node, x, y)
            else:
                self.logger.warning(f"Node coordinates file {coord_file} not found.")

            # Load origin-destination pairs
            od_file = os.path.join(analysis_dir, 'od_pairs.csv')
            if os.path.exists(od_file):
                od_pairs = pd.read_csv(od_file)

                # Add edges from OD pairs
                for _, row in od_pairs.iterrows():
                    origin = row['Origin']
                    dest = row['Destination']
                    time = row['MedianTimeSeconds']

                    # Ensure nodes exist
                    if origin not in new_hospital.graph.adjacency_list:
                        new_hospital.add_department(origin)
                    if dest not in new_hospital.graph.adjacency_list:
                        new_hospital.add_department(dest)

                    # Add edge
                    new_hospital.add_corridor(origin, dest, time)
            else:
                self.logger.warning(f"Origin-destination file {od_file} not found.")

            # Create a minimal analyzer for request generation patterns
            class MinimalAnalyzer:
                def __init__(self, od_file, hourly_dist=None):
                    self.od_pairs = []
                    self.median_times = {}
                    self.hourly_dist = hourly_dist or {}

                    # Load OD pairs
                    if os.path.exists(od_file):
                        od_data = pd.read_csv(od_file)
                        self.od_pairs = list(zip(od_data['Origin'], od_data['Destination']))

                        for _, row in od_data.iterrows():
                            self.median_times[(row['Origin'], row['Destination'])] = row['MedianTimeSeconds']

                def get_origin_destination_pairs(self):
                    return self.od_pairs

                def get_median_transport_times(self):
                    return self.median_times

                def get_hourly_request_distribution(self):
                    return self.hourly_dist

            # Create analyzer
            analyzer = MinimalAnalyzer(od_file)

            self.logger.info(f"Loaded analyzed data from {analysis_dir}")
            return new_hospital, analyzer

        except Exception as e:
            self.logger.error(f"Error loading analyzed data: {str(e)}")
            return None, None