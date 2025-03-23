import random


class RandomAssignment:

    def __init__(self, transporters, transport_requests, graph):
        self.transporters = transporters
        self.transport_requests = transport_requests
        self.graph = graph

    def generate_assignment_plan(self, transporters, requests):
        plan = {t.name: [] for t in transporters}
        available = list(transporters)

        for request in requests:
            if not available:
                available = list(transporters)
            transporter = random.choice(available)
            plan[transporter.name].append(request)

        return plan

    def estimate_travel_time(self, transporter, request):
            try:
                pathfinder = transporter.pathfinder
                graph = transporter.hospital.get_graph()

                # Time from current location to request origin
                path_to_origin, _ = pathfinder.dijkstra(transporter.current_location, request.origin)
                time_to_origin = sum(
                    graph.get_edge_weight(path_to_origin[i], path_to_origin[i + 1])
                    for i in range(len(path_to_origin) - 1)
                )

                # Time from origin to destination
                path_to_destination, _ = pathfinder.dijkstra(request.origin, request.destination)
                time_to_destination = sum(
                    graph.get_edge_weight(path_to_destination[i], path_to_destination[i + 1])
                    for i in range(len(path_to_destination) - 1)
                )

                return time_to_origin + time_to_destination
            except Exception:
                return 9999  # fallback if path can't be found
