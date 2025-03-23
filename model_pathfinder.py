import heapq


class Pathfinder:
    def __init__(self, hospital):
        """Initializes the pathfinder with a reference to the hospital graph."""
        self.hospital = hospital

    def dijkstra(self, start, end):
        """Finds the shortest path between two departments using Dijkstra's algorithm."""
        if not start or not end:
            raise ValueError("Start and end nodes must be specified and valid.")

        graph = self.hospital.get_graph().adjacency_list
        if start not in graph:
            raise ValueError(f"Start node '{start}' is not a valid node in the graph.")
        if end not in graph:
            raise ValueError(f"End node '{end}' is not a valid node in the graph.")

        priority_queue = []
        heapq.heappush(priority_queue, (0, start))  # (distance, node)
        distances = {node: float('inf') for node in graph}
        distances[start] = 0
        previous_nodes = {node: None for node in graph}

        while priority_queue:
            current_distance, current_node = heapq.heappop(priority_queue)

            # If the end node is reached, we can break, as the shortest path was found
            if current_node == end:
                break

            # Process all neighbors of the current node
            for neighbor, weight in graph[current_node].items():
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous_nodes[neighbor] = current_node
                    heapq.heappush(priority_queue, (distance, neighbor))

        # If the end node's distance is still infinity, no path exists
        if distances[end] == float('inf'):
            return [], float('inf')

        return self._reconstruct_path(previous_nodes, start, end), distances[end]

    def _reconstruct_path(self, previous_nodes, start, end):
        """Reconstructs the path from start to end."""
        path = []
        current = end
        while current is not None:
            path.append(current)
            current = previous_nodes.get(current)
            if current is None and path[-1] != start:
                # If current is None and we haven't reached the start node, break (invalid path)
                return []
        path.reverse()

        # Ensure the path starts with the start node
        return path if path[0] == start else []
