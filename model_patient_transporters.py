# patient_transporter.py
import time
from model_pathfinder import Pathfinder


class PatientTransporter:
    def __init__(self, hospital, name, start_location="Transporter Lounge"):
        """Initializes a transporter that moves patients and items between departments."""
        self.hospital = hospital
        self.name = name
        self.current_location = start_location  # Use start_location instead of hardcoding "Reception"
        self.workload = 0  # Tracks transporter workload
        self.pathfinder = Pathfinder(hospital)  # Pathfinder instance

    def move_to(self, destination):
        """Moves the transporter using the shortest path."""
        path, distance = self.pathfinder.dijkstra(self.current_location, destination)

        if path:
            self.workload += distance  # Increase workload based on shortest path distance
            print(f"{self.name} is moving along path: {' -> '.join(path)}. Total Workload: {self.workload}")
            self.current_location = destination
        else:
            print(f"{self.name} cannot reach {destination} from {self.current_location}.")

    def transport_item(self, item, destination):
        """Transports an item (patient, sample, equipment) using the shortest path."""
        path, distance = self.pathfinder.dijkstra(self.current_location, destination)

        if path:
            self.workload += distance * 1.5  # Increase workload more for transporting items
            print(
                f"{self.name} is transporting {item} along path: {' -> '.join(path)}. Total Workload: {self.workload}")
            self.current_location = destination
        else:
            print(f"{self.name} cannot transport {item} to {destination} from {self.current_location}.")

    def reduce_workload(self, amount=1):
        """Reduces workload over time when the transporter is idle."""
        while self.workload > 0:
            time.sleep(1)  # Simulating time passing
            self.workload = max(0, self.workload - amount)
            print(f"{self.name} is resting. Workload decreased to: {self.workload}")
