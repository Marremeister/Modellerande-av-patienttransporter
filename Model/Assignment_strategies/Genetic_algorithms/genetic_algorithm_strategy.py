from Model.Assignment_strategies.assignment_strategy import AssignmentStrategy
from Model.Assignment_strategies.Genetic_algorithms.genetic_algorithm import GeneticAlgorithm


class GeneticAlgorithmStrategy(AssignmentStrategy):
    """
    Strategy wrapper for the Genetic Algorithm optimizer.

    This strategy implements the AssignmentStrategy interface while delegating
    the actual optimization work to the GeneticAlgorithm class.
    """

    def __init__(self, population_size=50, generations=50, time_limit_seconds=5):
        """
        Initialize the genetic algorithm strategy.

        Args:
            population_size: Size of the population (default: 50)
            generations: Maximum number of generations to evolve (default: 50)
            time_limit_seconds: Maximum time in seconds to run (default: 5)
        """
        self.population_size = population_size
        self.generations = generations
        self.time_limit_seconds = time_limit_seconds
        self.algorithm = None

    def generate_assignment_plan(self, transporters, assignable_requests, graph):
        """
        Generate an assignment plan using genetic algorithm.

        Args:
            transporters: List of available transporters
            assignable_requests: List of requests to be assigned
            graph: Hospital graph with department locations

        Returns:
            Dictionary mapping transporter names to lists of assigned requests
        """
        # Scale parameters based on problem size
        self._scale_parameters(transporters, assignable_requests)

        # Create and run the algorithm
        self.algorithm = GeneticAlgorithm(
            transporters,
            assignable_requests,
            graph,
            population_size=self.population_size,
            generations=self.generations,
            time_limit_seconds=self.time_limit_seconds
        )

        # Run the algorithm and return the results
        return self.algorithm.run()

    def _scale_parameters(self, transporters, requests):
        """
        Scale strategy parameters based on problem size.

        Args:
            transporters: List of available transporters
            requests: List of requests to be assigned
        """
        # For very large problems, reduce population size and generations
        # to maintain reasonable performance
        if len(requests) > 100:
            self.population_size = min(self.population_size, 30)
            self.generations = min(self.generations, 30)

        # For smaller problems, we can afford larger populations
        elif len(requests) < 20:
            self.population_size = max(self.population_size, 100)
            self.generations = max(self.generations, 100)

        # Also scale time limit - more time for larger problems
        if len(requests) > 100:
            self.time_limit_seconds = max(self.time_limit_seconds, 10)

    def estimate_travel_time(self, transporter, request):
        """
        Estimate travel time for a transporter to complete a request.

        Args:
            transporter: Transporter object
            request: Transportation request object

        Returns:
            Estimated time in seconds
        """
        if not self.algorithm:
            # Create a temporary algorithm just for estimation
            self.algorithm = GeneticAlgorithm(
                [transporter], [request], transporter.hospital.get_graph()
            )

        return self.algorithm.estimate_travel_time(transporter, request)

    def get_optimizer(self, transporters, assignable_requests, graph):
        """
        Create and return a genetic algorithm instance.

        Args:
            transporters: List of available transporters
            assignable_requests: List of requests to be assigned
            graph: Hospital graph with department locations

        Returns:
            GeneticAlgorithm instance
        """
        self.algorithm = GeneticAlgorithm(
            transporters,
            assignable_requests,
            graph,
            population_size=self.population_size,
            generations=self.generations,
            time_limit_seconds=self.time_limit_seconds
        )
        return self.algorithm