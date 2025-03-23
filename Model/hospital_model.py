from Model.graph_model import Graph

class Hospital:
    def __init__(self):
        """Initializes a hospital graph with fixed node coordinates."""
        self.graph = Graph(directed=False)
        self.departments = []
        self.department_positions = {  # NEW: Fixed positions for each department
            "Emergency": (100, 100), "ICU": (300, 100), "Surgery": (500, 100),
            "Radiology": (700, 100), "Reception": (100, 300), "Pediatrics": (300, 300),
            "Orthopedics": (500, 300), "Cardiology": (700, 300), "Neurology": (100, 500),
            "Pharmacy": (300, 500), "Laboratory": (500, 500), "General Ward": (700, 500),
            "Cafeteria": (100, 700), "Admin Office": (300, 700), "Transporter Lounge": (500, 700)
        }

    def add_department(self, department):
        """Adds a department to the hospital and assigns a fixed position."""
        if department not in self.departments:
            self.departments.append(department)
            x, y = self.department_positions.get(department, (0, 0))  # Default to (0,0) if not found
            self.graph.add_node(department, x, y)  # Store position

    def add_corridor(self, dept1, dept2, distance):
        """Adds a corridor (edge) between two departments."""
        self.graph.add_edge(dept1, dept2, distance)

    def get_graph(self):
        """Returns the internal graph representation."""
        return self.graph
