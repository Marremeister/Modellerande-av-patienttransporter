import time
import eventlet
from model_pathfinder import Pathfinder


class PatientTransporter:
    def __init__(self, hospital, name, socketio, start_location="Transporter Lounge"):
        """Initializes a transporter for moving patients/items between departments."""
        self.hospital = hospital
        self.name = name
        self.current_location = start_location
        self.workload = 0  # Tracks workload
        self.status = "active"  # 🚀 Transporters start as active by default
        self.pathfinder = Pathfinder(hospital)  # Pathfinder instance
        self.socketio = socketio  # WebSocket connection for real-time updates

    def set_active(self):
        """Sets the transporter as active (available for assignments)."""
        self.status = "active"
        self.socketio.emit("transporter_status_update", {"name": self.name, "status": "active"})
        print(f"✅ {self.name} is now ACTIVE.")

    def set_inactive(self):
        """Sets the transporter as inactive (on break, unavailable for assignments)."""
        self.status = "inactive"
        self.socketio.emit("transporter_status_update", {"name": self.name, "status": "inactive"})
        print(f"⏸️ {self.name} is now INACTIVE.")

    def move_to(self, destination):
        """Moves the transporter step-by-step using the shortest path."""
        if self.status == "inactive":
            print(f"❌ {self.name} is inactive and cannot move.")
            return

        path, total_distance = self.pathfinder.dijkstra(self.current_location, destination)
        if not path:
            print(f"⚠️ {self.name} cannot reach {destination} from {self.current_location}.")
            return

        print(f"🚶 {self.name} moving along path: {' -> '.join(path)}")

        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]

            # Get edge weight (travel time)
            travel_time = self.hospital.get_graph().get_edge_weight(current_node, next_node)

            # Simulate movement step
            eventlet.sleep(travel_time)
            self.current_location = next_node
            self.socketio.emit("transporter_update", {"name": self.name, "location": next_node})

            print(f"📍 {self.name} arrived at {next_node} (Travel time: {travel_time}s)")

        # Update workload after transport
        self.workload += total_distance
        print(f"🔄 {self.name}'s workload increased to {self.workload}.")

    def transport_item(self, item, destination):
        """Transports an item to the destination with a higher workload impact."""
        if self.status == "inactive":
            print(f"❌ {self.name} is inactive and cannot transport items.")
            return

        path, total_distance = self.pathfinder.dijkstra(self.current_location, destination)
        if not path:
            print(f"⚠️ {self.name} cannot transport {item} to {destination}.")
            return

        print(f"🚛 {self.name} transporting {item} along path: {' -> '.join(path)}")

        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]

            travel_time = self.hospital.get_graph().get_edge_weight(current_node, next_node)

            eventlet.sleep(travel_time)
            self.current_location = next_node
            self.socketio.emit("transporter_update", {"name": self.name, "location": next_node})

            print(f"📍 {self.name} delivered {item} to {next_node} (Travel time: {travel_time}s)")

        # Increase workload more for transporting items
        self.workload += total_distance * 1.5
        print(f"🔄 {self.name}'s workload increased to {self.workload}.")

    def reduce_workload(self, amount=1):
        """Simulates workload recovery over time when idle."""
        while self.workload > 0:
            eventlet.sleep(1)
            self.workload = max(0, self.workload - amount)
            print(f"💤 {self.name} is resting. Workload: {self.workload}")

