import eventlet
from Model.model_pathfinder import Pathfinder
from Model.model_shift_manager import ShiftManager

class PatientTransporter:
    def __init__(self, hospital, name, socketio, start_location="Transporter Lounge"):
        """Initializes a transporter that moves patients and items between departments."""
        self.hospital = hospital
        self.name = name
        self.current_location = start_location
        self.status = "active"  # Can be "active" or "inactive"
        self.workload = 0  # Total workload
        self.pathfinder = Pathfinder(hospital)
        self.socketio = socketio  # For sending updates
        self.current_task = None
        self.task_queue = []
        self.is_busy = False
        self.shift_manager = ShiftManager(self)

    def set_active(self):
        """Sets transporter to active."""
        self.status = "active"
        self.socketio.emit("transporter_status_update", {"name": self.name, "status": "active"})

    def set_inactive(self):
        """Sets transporter to inactive."""
        self.status = "inactive"
        self.socketio.emit("transporter_status_update", {"name": self.name, "status": "inactive"})

    def move_to(self, destination):
        """Moves the transporter step by step, updating location and workload with edge-based timing."""
        if self.status == "inactive":
            print(f"🚫 {self.name} is inactive and cannot move.")
            return False

        path, distance = self.pathfinder.dijkstra(self.current_location, destination)
        if not path:
            print(f"❌ {self.name} cannot reach {destination} from {self.current_location}.")
            return False

        self.increase_workload(distance)

        durations_ms = []
        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]
            travel_time = self.hospital.get_graph().get_edge_weight(current_node, next_node)
            durations_ms.append(travel_time * 1000)

        # Emit entire path + durations once, for frontend to animate
        self.socketio.emit("transporter_update", {
            "name": self.name,
            "path": path,
            "durations": durations_ms
        })


        # Simulate delay in backend
        for travel_time in durations_ms:
            seconds = travel_time / 1000.0
            self.shift_manager.update_work_time(seconds)
            eventlet.sleep(seconds)

        # Update to final position
        self.current_location = path[-1]

        return True

    def increase_workload(self, amount):
        """Increases workload based on the transport distance."""
        self.workload += amount

        self.socketio.emit("workload_update", {"name": self.name, "workload": self.workload})

    def reduce_workload(self, amount=1):
        """Reduces workload over time when the transporter is idle."""
        while self.workload > 0:
            eventlet.sleep(1)  # Simulating time passing
            self.workload = max(0, self.workload - amount)
            self.socketio.emit("workload_update", {"name": self.name, "workload": self.workload})

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "current_location": self.current_location,
            "workload": self.workload
        }

