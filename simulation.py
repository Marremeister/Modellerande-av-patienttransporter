import random
import eventlet

class Simulation:
    def __init__(self, system, socketio, interval=10):
        self.system = system
        self.socketio = socketio
        self.interval = interval
        self.running = False

    def start(self):
        """Starts the simulation in the background."""
        self.running = True
        eventlet.spawn_n(self._run_loop)

    def stop(self):
        """Stops the simulation loop."""
        self.running = False

    def _run_loop(self):
        """Main simulation loop."""
        graph = self.system.hospital.get_graph()
        locations = list(graph.get_nodes())

        while self.running:
            origin, destination = random.sample(locations, 2)
            transport_type = random.choice(["stretcher", "wheelchair", "bed"])
            urgent = random.choice([True, False])

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

            print(f"🧪 [Simulation] Request: {origin} ➝ {destination} ({transport_type}, urgent={urgent})")

            self.system.deploy_optimization()

            eventlet.sleep(self.interval)
