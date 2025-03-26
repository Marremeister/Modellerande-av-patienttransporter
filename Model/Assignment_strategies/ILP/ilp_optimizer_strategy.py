from Model.Assignment_strategies.assignment_strategy import AssignmentStrategy
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode

# Import ILP implementations
from Model.Assignment_strategies.ILP.ilp_makespan import ILPMakespan
from Model.Assignment_strategies.ILP.ilp_equal_workload import ILPEqualWorkload
from Model.Assignment_strategies.ILP.ilp_urgency_first import ILPUrgencyFirst
from Model.Assignment_strategies.ILP.cluster_based_ilp import ClusterBasedILP


class ILPOptimizerStrategy(AssignmentStrategy):
    def __init__(self, mode=ILPMode.MAKESPAN, **kwargs):
        """
        Initialize with an ILP mode.

        Args:
            mode: The ILP mode to use (from ILPMode enum)
            **kwargs: Additional parameters for specific modes (e.g., num_clusters)
        """
        self.mode = mode
        self.kwargs = kwargs
        self.optimizer = None

    def generate_assignment_plan(self, transporters, assignable_requests, graph):
        self.optimizer = self.get_optimizer(transporters, assignable_requests, graph)
        return self.optimizer.build_and_solve()

    def get_optimizer(self, transporters, assignable_requests, graph):
        """
        Create and return an ILP optimizer based on the selected mode.

        Args:
            transporters: List of available transporters
            assignable_requests: List of requests to be assigned
            graph: Hospital graph

        Returns:
            ILP optimizer instance
        """
        if self.mode == ILPMode.MAKESPAN:
            return ILPMakespan(transporters, assignable_requests, graph)
        elif self.mode == ILPMode.EQUAL_WORKLOAD:
            return ILPEqualWorkload(transporters, assignable_requests, graph)
        elif self.mode == ILPMode.URGENCY_FIRST:
            return ILPUrgencyFirst(transporters, assignable_requests, graph)
        elif self.mode == ILPMode.CLUSTER_BASED:
            # Get parameters specific to cluster-based approach
            num_clusters = self.kwargs.get('num_clusters', 5)
            return ClusterBasedILP(transporters, assignable_requests, graph, num_clusters=num_clusters)
        else:
            raise ValueError(f"Unsupported ILP Mode: {self.mode}")

    def estimate_travel_time(self, transporter, request):
        if not self.optimizer:
            raise RuntimeError("ILPOptimizerStrategy: optimizer not initialized.")
        return self.optimizer.estimate_travel_time(transporter, request)