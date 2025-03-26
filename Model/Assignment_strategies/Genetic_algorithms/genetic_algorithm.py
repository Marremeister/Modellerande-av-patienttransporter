import random
import numpy as np
import time
import logging
from copy import deepcopy
import statistics
from collections import defaultdict


class GeneticAlgorithm:
    """
    Enhanced Genetic Algorithm for transport assignment optimization.

    Features:
    - Multiple selection methods (tournament, roulette wheel)
    - Various crossover operators (one-point, two-point, uniform)
    - Adaptive mutation rates
    - Multiple fitness functions (makespan, workload balance, urgency)
    - Early stopping criteria
    - Population diversity maintenance
    - Detailed performance metrics
    - Progress callback
    """

    def __init__(self, transporters, requests, graph,
                 population_size=50, generations=50, time_limit_seconds=5,
                 mutation_rate=0.1, crossover_rate=0.8, selection_method="tournament",
                 crossover_method="two_point", fitness_weights=None,
                 early_stopping=True, debug_mode=False, progress_callback=None):
        """
        Initialize the genetic algorithm optimizer.

        Args:
            transporters: List of transporter objects
            requests: List of request objects
            graph: Hospital graph with department locations
            population_size: Size of the population to evolve
            generations: Maximum number of generations to evolve
            time_limit_seconds: Maximum time in seconds to run
            mutation_rate: Initial mutation rate (0.0-1.0)
            crossover_rate: Probability of crossover (0.0-1.0)
            selection_method: Method for parent selection ("tournament" or "roulette")
            crossover_method: Type of crossover ("one_point", "two_point", "uniform")
            fitness_weights: Dict with weights for different fitness components
                             (makespan, balance, urgency)
            early_stopping: Whether to use early stopping if no improvement
            debug_mode: Enable detailed logging
            progress_callback: Function to call with progress updates
        """
        self.transporters = transporters
        self.requests = requests
        self.graph = graph

        # Algorithm parameters
        self.population_size = min(max(population_size, 20), 200)
        self.generations = generations
        self.time_limit_seconds = time_limit_seconds
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.selection_method = selection_method
        self.crossover_method = crossover_method
        self.early_stopping = early_stopping
        self.debug_mode = debug_mode
        self.progress_callback = progress_callback

        # Set default fitness weights if not provided
        if fitness_weights is None:
            self.fitness_weights = {
                "makespan": 1.0,  # Weight for minimizing maximum completion time
                "balance": 0.3,  # Weight for workload balance
                "urgency": 0.5,  # Weight for prioritizing urgent requests
                "travel_efficiency": 0.2  # Weight for minimizing total travel time
            }
        else:
            self.fitness_weights = fitness_weights

        # Setup logging
        self._setup_logging()

        # Initialize state
        self.best_solution = None
        self.best_fitness = float('inf')
        self.best_generation = 0
        self.current_generation = 0
        self.population = []

        # Performance metrics
        self.initialization_time = 0
        self.evolution_time = 0
        self.fitness_eval_time = 0
        self.selection_time = 0
        self.crossover_time = 0
        self.mutation_time = 0
        self.total_time = 0
        self.fitness_history = []
        self.diversity_history = []

        # Cache for path calculations
        self.path_cache = {}

    def _setup_logging(self):
        """Set up logging for the optimizer."""
        self.logger = logging.getLogger('GeneticAlgorithm')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)

    def run(self):
        """
        Run the genetic algorithm optimization process.

        Returns:
            dict: Assignment plan mapping transporter names to lists of requests
        """
        start_time = time.time()
        self.total_time = 0

        # For small problems, use a simple greedy algorithm
        if len(self.requests) <= 8:
            self.logger.info(f"Small problem detected ({len(self.requests)} requests). Using greedy algorithm.")
            plan = self._solve_greedy()
            self.total_time = time.time() - start_time
            return plan

        # Initialize population
        init_start = time.time()
        self.population = self._initialize_population()
        self.initialization_time = time.time() - init_start

        # Initial fitness evaluation
        fitness_start = time.time()
        fitness_scores = self._evaluate_population_fitness(self.population)
        self.fitness_eval_time = time.time() - fitness_start

        # Find initial best solution
        best_idx = np.argmin(fitness_scores)
        self.best_fitness = fitness_scores[best_idx]
        self.best_solution = self.population[best_idx]
        self.best_generation = 0

        self.logger.info(f"Initial population: size={len(self.population)}, best fitness={self.best_fitness:.2f}")

        # Record initial metrics
        self.fitness_history.append(self.best_fitness)
        diversity = self._calculate_population_diversity(self.population)
        self.diversity_history.append(diversity)

        # Main evolution loop
        evolution_start = time.time()

        for generation in range(self.generations):
            self.current_generation = generation

            # Check time limit
            if time.time() - start_time > self.time_limit_seconds:
                self.logger.info(f"Time limit reached after {generation} generations")
                break

            # Select parents for reproduction
            selection_start = time.time()
            parents = self._select_parents(self.population, fitness_scores)
            self.selection_time += time.time() - selection_start

            # Create next generation through crossover and mutation
            next_generation = []

            # Add elite individuals directly to next generation (elitism)
            elite_count = max(1, self.population_size // 10)  # Top 10% are elite
            elite_indices = np.argsort(fitness_scores)[:elite_count]
            elites = [self.population[i] for i in elite_indices]
            next_generation.extend(elites)

            # Fill the rest of the population with new offspring
            crossover_start = time.time()
            while len(next_generation) < self.population_size:
                # Select parents for this offspring
                parent1, parent2 = random.sample(parents, 2)

                # Crossover with probability
                if random.random() < self.crossover_rate:
                    child = self._crossover(parent1, parent2)
                else:
                    child = deepcopy(parent1)

                next_generation.append(child)
            self.crossover_time += time.time() - crossover_start

            # Apply mutation to all except elites
            mutation_start = time.time()
            for i in range(elite_count, len(next_generation)):
                if random.random() < self.mutation_rate:
                    next_generation[i] = self._mutate(next_generation[i])
            self.mutation_time += time.time() - mutation_start

            # Replace population
            self.population = next_generation

            # Evaluate new population
            fitness_start = time.time()
            fitness_scores = self._evaluate_population_fitness(self.population)
            self.fitness_eval_time += time.time() - fitness_start

            # Update best solution
            min_fitness = min(fitness_scores)
            min_idx = fitness_scores.index(min_fitness)

            if min_fitness < self.best_fitness:
                self.best_fitness = min_fitness
                self.best_solution = self.population[min_idx]
                self.best_generation = generation
                self.logger.debug(f"New best: gen={generation}, fitness={min_fitness:.2f}")

            # Record metrics for this generation
            self.fitness_history.append(min_fitness)
            diversity = self._calculate_population_diversity(self.population)
            self.diversity_history.append(diversity)

            # Report progress
            if self.progress_callback and generation % 5 == 0:
                progress = {
                    "generation": generation,
                    "max_generations": self.generations,
                    "best_fitness": self.best_fitness,
                    "current_diversity": diversity,
                    "time_elapsed": time.time() - start_time
                }
                self.progress_callback(progress)

            # Early stopping check
            if self.early_stopping and generation - self.best_generation > 20:
                # If no improvement in 20 generations, and diversity is low
                if diversity < 0.1:  # Low diversity threshold
                    self.logger.info(f"Early stopping at generation {generation}: "
                                     f"No improvement in 20 generations and low diversity")
                    break

            # Adaptive mutation rate adjustment
            self._adjust_mutation_rate(generation)

            # Diversity maintenance
            if diversity < 0.05 and generation < self.generations - 10:
                self.logger.debug(f"Low diversity ({diversity:.3f}). Injecting new chromosomes.")
                self._inject_diversity()

        self.evolution_time = time.time() - evolution_start
        self.total_time = time.time() - start_time

        # Convert best solution to plan
        plan = self._convert_to_plan(self.best_solution)

        # Log performance
        self._log_performance()

        return plan

    def _initialize_population(self):
        """
        Create initial population with a mix of heuristic and random solutions.

        Returns:
            list: Initial population of chromosomes
        """
        self.logger.debug("Initializing population")
        population = []

        # Create one individual with greedy algorithm
        greedy_plan = self._solve_greedy()
        greedy_chromosome = self._plan_to_chromosome(greedy_plan)
        population.append(greedy_chromosome)

        # Create one individual with urgency-first heuristic
        urgency_plan = self._solve_urgency_first()
        urgency_chromosome = self._plan_to_chromosome(urgency_plan)
        population.append(urgency_chromosome)

        # Create one individual with load-balancing heuristic
        balance_plan = self._solve_balanced()
        balance_chromosome = self._plan_to_chromosome(balance_plan)
        population.append(balance_chromosome)

        # Create random individuals for the rest of the population
        while len(population) < self.population_size:
            chromosome = self._create_random_chromosome()
            population.append(chromosome)

        return population

    def _create_random_chromosome(self):
        """Create a random assignment chromosome."""
        # Create a random chromosome: a list where the index corresponds to a request
        # and the value is the index of the assigned transporter
        return [random.randrange(len(self.transporters)) for _ in range(len(self.requests))]

    def _plan_to_chromosome(self, plan):
        """
        Convert a plan dict to a chromosome representation.

        Args:
            plan: Dict mapping transporter names to request lists

        Returns:
            list: Chromosome representation
        """
        chromosome = [0] * len(self.requests)

        for t_idx, transporter in enumerate(self.transporters):
            requests = plan.get(transporter.name, [])
            for request in requests:
                req_idx = self.requests.index(request) if request in self.requests else -1
                if req_idx >= 0:
                    chromosome[req_idx] = t_idx

        return chromosome

    def _evaluate_population_fitness(self, population):
        """
        Evaluate fitness for all individuals in the population.

        Args:
            population: List of chromosomes

        Returns:
            list: Fitness scores (lower is better)
        """
        return [self._evaluate_fitness(chrom) for chrom in population]

    def _evaluate_fitness(self, chromosome):
        """
        Evaluate the fitness of a single chromosome.

        Args:
            chromosome: Assignment chromosome

        Returns:
            float: Fitness score (lower is better)
        """
        # Initialize fitness components
        makespan = 0
        total_travel_time = 0
        max_urgent_completion_time = 0

        # Track workload and completion times per transporter
        workloads = {t.name: 0 for t in self.transporters}
        current_locations = {t.name: t.current_location for t in self.transporters}
        urgent_completion_times = []

        # Process each request
        for i, t_idx in enumerate(chromosome):
            if t_idx >= len(self.transporters):
                # Invalid assignment - high penalty
                return float('inf')

            transporter = self.transporters[t_idx]
            request = self.requests[i]

            # Calculate travel times
            to_origin_time = self._estimate_point_to_point_time(
                current_locations[transporter.name], request.origin
            )

            to_dest_time = self._estimate_point_to_point_time(
                request.origin, request.destination
            )

            # Update state
            completion_time = workloads[transporter.name] + to_origin_time + to_dest_time
            workloads[transporter.name] = completion_time
            current_locations[transporter.name] = request.destination

            # Track total travel time
            total_travel_time += to_origin_time + to_dest_time

            # Track urgent request completion times
            if hasattr(request, 'urgent') and request.urgent:
                urgent_completion_times.append(completion_time)

        # Calculate makespan (max completion time)
        makespan = max(workloads.values()) if workloads else 0

        # Calculate workload balance (standard deviation)
        workload_values = list(workloads.values())
        workload_std = np.std(workload_values) if len(workload_values) > 1 else 0

        # Calculate urgent request penalty (avg completion time for urgent requests)
        urgent_penalty = max(urgent_completion_times) if urgent_completion_times else 0

        # Travel efficiency (average travel time per request)
        travel_efficiency = total_travel_time / max(1, len(self.requests))

        # Combine components with weights
        fitness = (
                self.fitness_weights["makespan"] * makespan +
                self.fitness_weights["balance"] * workload_std +
                self.fitness_weights["urgency"] * urgent_penalty +
                self.fitness_weights["travel_efficiency"] * travel_efficiency
        )

        return fitness

    def _select_parents(self, population, fitness_scores):
        """
        Select parents for reproduction using the selected selection method.

        Args:
            population: List of chromosomes
            fitness_scores: List of corresponding fitness scores

        Returns:
            list: Selected parent chromosomes
        """
        if self.selection_method == "tournament":
            return self._tournament_selection(population, fitness_scores)
        elif self.selection_method == "roulette":
            return self._roulette_wheel_selection(population, fitness_scores)
        else:
            self.logger.warning(f"Unknown selection method: {self.selection_method}, using tournament")
            return self._tournament_selection(population, fitness_scores)

    def _tournament_selection(self, population, fitness_scores):
        """
        Select parents using tournament selection.

        Args:
            population: List of chromosomes
            fitness_scores: List of corresponding fitness scores

        Returns:
            list: Selected parent chromosomes
        """
        parents = []
        tournament_size = max(2, self.population_size // 5)

        num_parents = max(self.population_size // 2, 4)  # At least 4 parents

        while len(parents) < num_parents:
            # Select random candidates for tournament
            candidates = random.sample(range(len(population)), min(tournament_size, len(population)))

            # Find the best candidate
            best_idx = min(candidates, key=lambda i: fitness_scores[i])
            parents.append(deepcopy(population[best_idx]))

        return parents

    def _roulette_wheel_selection(self, population, fitness_scores):
        """
        Select parents using roulette wheel selection.

        Args:
            population: List of chromosomes
            fitness_scores: List of corresponding fitness scores

        Returns:
            list: Selected parent chromosomes
        """
        # Since fitness is minimized, invert scores so better solutions have higher weight
        if not fitness_scores or max(fitness_scores) == float('inf'):
            # Fallback to random selection if all fitness scores are infinite
            return random.choices(population, k=max(4, self.population_size // 2))

        max_fitness = max(fitness_scores)
        inverted_fitness = [max(0.001, max_fitness - score + 0.001) for score in fitness_scores]
        total_fitness = sum(inverted_fitness)

        # Normalize to probabilities
        selection_probs = [f / total_fitness for f in inverted_fitness]

        # Select parents
        num_parents = max(self.population_size // 2, 4)  # At least 4 parents
        parents = random.choices(population, weights=selection_probs, k=num_parents)

        return [deepcopy(p) for p in parents]

    def _crossover(self, parent1, parent2):
        """
        Create a child by combining parts of two parents using the selected method.

        Args:
            parent1: First parent chromosome
            parent2: Second parent chromosome

        Returns:
            list: Child chromosome
        """
        if self.crossover_method == "one_point":
            return self._one_point_crossover(parent1, parent2)
        elif self.crossover_method == "two_point":
            return self._two_point_crossover(parent1, parent2)
        elif self.crossover_method == "uniform":
            return self._uniform_crossover(parent1, parent2)
        else:
            self.logger.warning(f"Unknown crossover method: {self.crossover_method}, using two-point")
            return self._two_point_crossover(parent1, parent2)

    def _one_point_crossover(self, parent1, parent2):
        """Perform one-point crossover."""
        if len(parent1) <= 1:
            return deepcopy(parent1)

        crossover_point = random.randrange(1, len(parent1))
        return parent1[:crossover_point] + parent2[crossover_point:]

    def _two_point_crossover(self, parent1, parent2):
        """Perform two-point crossover."""
        if len(parent1) <= 2:
            return deepcopy(parent1)

        point1 = random.randrange(len(parent1) - 1)
        point2 = random.randrange(point1 + 1, len(parent1))

        return parent1[:point1] + parent2[point1:point2] + parent1[point2:]

    def _uniform_crossover(self, parent1, parent2):
        """Perform uniform crossover with 50% probability for each gene."""
        child = []
        for i in range(len(parent1)):
            if random.random() < 0.5:
                child.append(parent1[i])
            else:
                child.append(parent2[i])
        return child

    def _mutate(self, chromosome):
        """
        Apply mutation operators to a chromosome.

        Args:
            chromosome: Chromosome to mutate

        Returns:
            list: Mutated chromosome
        """
        # Choose mutation type based on random choice and chromosome length
        mutation_types = []

        # For small chromosomes (few requests), prefer point mutation
        if len(chromosome) <= 10:
            mutation_types = ["point"] * 4 + ["swap", "inversion"]
        # For medium chromosomes, use a mix
        elif len(chromosome) <= 30:
            mutation_types = ["point"] * 2 + ["swap"] * 2 + ["inversion", "scramble"]
        # For large chromosomes, use more powerful operators
        else:
            mutation_types = ["point", "swap"] * 2 + ["inversion", "scramble"] * 2

        mutation_type = random.choice(mutation_types)

        if mutation_type == "point":
            return self._point_mutation(chromosome)
        elif mutation_type == "swap":
            return self._swap_mutation(chromosome)
        elif mutation_type == "inversion":
            return self._inversion_mutation(chromosome)
        elif mutation_type == "scramble":
            return self._scramble_mutation(chromosome)
        else:
            return self._point_mutation(chromosome)  # Default

    def _point_mutation(self, chromosome):
        """Change random positions to random transporters."""
        mutated = deepcopy(chromosome)
        num_mutations = max(1, int(len(chromosome) * self.mutation_rate))
        positions = random.sample(range(len(chromosome)), min(num_mutations, len(chromosome)))

        for pos in positions:
            mutated[pos] = random.randrange(len(self.transporters))

        return mutated

    def _swap_mutation(self, chromosome):
        """Swap the transporters for two random requests."""
        if len(chromosome) <= 1:
            return deepcopy(chromosome)

        mutated = deepcopy(chromosome)
        pos1, pos2 = random.sample(range(len(chromosome)), 2)
        mutated[pos1], mutated[pos2] = mutated[pos2], mutated[pos1]

        return mutated

    def _inversion_mutation(self, chromosome):
        """Invert a section of the chromosome."""
        if len(chromosome) <= 2:
            return deepcopy(chromosome)

        mutated = deepcopy(chromosome)

        # Select section to invert
        start = random.randrange(len(chromosome) - 1)
        end = random.randrange(start + 1, min(start + 10, len(chromosome)))

        # Invert section
        mutated[start:end] = mutated[start:end][::-1]

        return mutated

    def _scramble_mutation(self, chromosome):
        """Randomly scramble a section of the chromosome."""
        if len(chromosome) <= 2:
            return deepcopy(chromosome)

        mutated = deepcopy(chromosome)

        # Select section to scramble
        start = random.randrange(len(chromosome) - 1)
        end = random.randrange(start + 1, min(start + 10, len(chromosome)))

        # Extract section
        section = mutated[start:end]
        random.shuffle(section)

        # Replace section
        mutated[start:end] = section

        return mutated

    def _calculate_population_diversity(self, population):
        """
        Calculate population diversity using average Hamming distance.

        Args:
            population: List of chromosomes

        Returns:
            float: Diversity measure (0.0-1.0)
        """
        if not population or len(population) <= 1:
            return 0.0

        # Sample pairs for large populations
        num_pairs = min(100, len(population) * (len(population) - 1) // 2)
        total_distance = 0

        if len(population) <= 15:  # Small population, check all pairs
            for i in range(len(population)):
                for j in range(i + 1, len(population)):
                    distance = sum(c1 != c2 for c1, c2 in zip(population[i], population[j]))
                    total_distance += distance

            max_possible = len(population[0]) * (len(population) * (len(population) - 1) // 2)
            return total_distance / max_possible if max_possible > 0 else 0.0
        else:  # Larger population, sample pairs
            pairs_sampled = 0
            while pairs_sampled < num_pairs:
                i, j = random.sample(range(len(population)), 2)
                distance = sum(c1 != c2 for c1, c2 in zip(population[i], population[j]))
                total_distance += distance
                pairs_sampled += 1

            max_possible = len(population[0]) * num_pairs
            return total_distance / max_possible if max_possible > 0 else 0.0

    def _adjust_mutation_rate(self, generation):
        """
        Dynamically adjust mutation rate based on progress and diversity.

        Args:
            generation: Current generation number
        """
        # Only adjust every 5 generations
        if generation % 5 != 0:
            return

        # Check if we're making progress by looking at recent fitness history
        recent_history = self.fitness_history[-5:] if len(self.fitness_history) >= 5 else self.fitness_history

        if len(recent_history) >= 3:
            # Calculate improvement rate
            improvements = [recent_history[i] - recent_history[i + 1] for i in range(len(recent_history) - 1)]
            avg_improvement = sum(improvements) / len(improvements)

            # Check diversity
            latest_diversity = self.diversity_history[-1] if self.diversity_history else 0.5

            # If low improvement and low diversity, increase mutation
            if avg_improvement < 0.01 * self.best_fitness and latest_diversity < 0.2:
                new_rate = min(0.3, self.mutation_rate * 1.5)
                if new_rate != self.mutation_rate:
                    self.logger.debug(f"Increasing mutation rate: {self.mutation_rate:.3f} -> {new_rate:.3f}")
                    self.mutation_rate = new_rate

            # If good improvement, slightly decrease mutation
            elif avg_improvement > 0.05 * self.best_fitness:
                new_rate = max(0.01, self.mutation_rate * 0.9)
                if new_rate != self.mutation_rate:
                    self.logger.debug(f"Decreasing mutation rate: {self.mutation_rate:.3f} -> {new_rate:.3f}")
                    self.mutation_rate = new_rate

    def _inject_diversity(self):
        """Inject diversity by replacing some individuals with new random ones."""
        # Replace bottom 20% of population with new random individuals
        if len(self.population) <= 3:
            return

        # Evaluate current population
        fitness_scores = self._evaluate_population_fitness(self.population)

        # Find indices of worst individuals
        num_to_replace = max(1, self.population_size // 5)
        worst_indices = np.argsort(fitness_scores)[-num_to_replace:]

        # Create new random individuals
        for idx in worst_indices:
            self.population[idx] = self._create_random_chromosome()

        self.logger.debug(f"Injected {num_to_replace} new random individuals")

    def _convert_to_plan(self, chromosome):
        """
        Convert a chromosome to an assignment plan dict.

        Args:
            chromosome: Assignment chromosome

        Returns:
            dict: Assignment plan mapping transporter names to request lists
        """
        plan = {t.name: [] for t in self.transporters}

        for i, t_idx in enumerate(chromosome):
            if t_idx >= len(self.transporters):
                continue  # Skip invalid assignments

            transporter = self.transporters[t_idx]
            request = self.requests[i]
            plan[transporter.name].append(request)

        # Sort each transporter's requests into an efficient route
        for t in self.transporters:
            if plan[t.name]:
                plan[t.name] = self._sort_requests_by_greedy_chain(t, plan[t.name])

        return plan

    def _solve_greedy(self):
        """
        Solve the assignment problem using a simple greedy algorithm.

        Returns:
            dict: Assignment plan mapping transporter names to request lists
        """
        self.logger.debug("Solving with greedy algorithm")
        plan = {t.name: [] for t in self.transporters}

        # Track current workload and location for each transporter
        workloads = {t.name: 0 for t in self.transporters}
        locations = {t.name: t.current_location for t in self.transporters}

        # Sort requests by urgency (if available)
        sorted_requests = sorted(
            self.requests,
            key=lambda r: not getattr(r, 'urgent', False)  # Urgent requests first
        )

        # Assign each request to the transporter that can complete it the fastest
        for request in sorted_requests:
            best_transporter = None
            min_additional_time = float('inf')

            for transporter in self.transporters:
                # Calculate additional time for this transporter to handle this request
                time_to_origin = self._estimate_point_to_point_time(
                    locations[transporter.name], request.origin
                )
                time_to_dest = self._estimate_point_to_point_time(
                    request.origin, request.destination
                )
                additional_time = time_to_origin + time_to_dest

                # Factor in current workload
                total_time = workloads[transporter.name] + additional_time

                # Check if this is the best option so far
                if total_time < min_additional_time:
                    min_additional_time = total_time
                    best_transporter = transporter

            # Assign to the best transporter
            if best_transporter:
                plan[best_transporter.name].append(request)

                # Update workload and location
                time_to_origin = self._estimate_point_to_point_time(
                    locations[best_transporter.name], request.origin
                )
                time_to_dest = self._estimate_point_to_point_time(
                    request.origin, request.destination
                )
                workloads[best_transporter.name] += time_to_origin + time_to_dest
                locations[best_transporter.name] = request.destination

        return plan

    def _solve_urgency_first(self):
        """
        Solve with urgent requests prioritized for fastest transporters.

        Returns:
            dict: Assignment plan
        """
        self.logger.debug("Solving with urgency-first algorithm")
        plan = {t.name: [] for t in self.transporters}

        # Separate urgent and non-urgent requests
        urgent_requests = [r for r in self.requests if getattr(r, 'urgent', False)]
        regular_requests = [r for r in self.requests if not getattr(r, 'urgent', False)]

        # Calculate transporters' base speed (average time per unit distance)
        transporter_speeds = self._calculate_transporter_speeds()

        # Sort transporters by speed (fastest first)
        sorted_transporters = sorted(
            self.transporters,
            key=lambda t: transporter_speeds.get(t.name, float('inf'))
        )

        # Create equal groups of transporters
        num_groups = 3  # Fast, medium, slow
        group_size = max(1, len(sorted_transporters) // num_groups)
        transporter_groups = []

        for i in range(0, len(sorted_transporters), group_size):
            group = sorted_transporters[i:i + group_size]
            if group:
                transporter_groups.append(group)

        # Ensure we have at least one group
        if not transporter_groups:
            transporter_groups = [sorted_transporters]

        # Assign urgent requests to fastest group first
        if urgent_requests and transporter_groups:
            fast_group = transporter_groups[0]

            # Track current location and workload
            locations = {t.name: t.current_location for t in fast_group}
            workloads = {t.name: 0 for t in fast_group}

            # Assign each urgent request to least busy transporter in fast group
            for request in urgent_requests:
                best_transporter = min(fast_group, key=lambda t: workloads[t.name])

                # Add to plan
                plan[best_transporter.name].append(request)

                # Update workload and location
                time_to_origin = self._estimate_point_to_point_time(
                    locations[best_transporter.name], request.origin
                )
                time_to_dest = self._estimate_point_to_point_time(
                    request.origin, request.destination
                )
                workloads[best_transporter.name] += time_to_origin + time_to_dest
                locations[best_transporter.name] = request.destination

        # Assign remaining requests using greedy approach
        # Track all transporters' workload and location
        locations = {t.name: t.current_location for t in self.transporters}
        workloads = {t.name: 0 for t in self.transporters}

        # Update based on urgent assignments
        for t_name, requests in plan.items():
            if not requests:
                continue

            transporter = next(t for t in self.transporters if t.name == t_name)
            current_location = transporter.current_location

            for req in requests:
                time_to_origin = self._estimate_point_to_point_time(current_location, req.origin)
                time_to_dest = self._estimate_point_to_point_time(req.origin, req.destination)

                workloads[t_name] += time_to_origin + time_to_dest
                current_location = req.destination

            locations[t_name] = current_location

        # Assign regular requests
        for request in regular_requests:
            best_transporter = None
            min_completion_time = float('inf')

            for transporter in self.transporters:
                # Calculate completion time
                time_to_origin = self._estimate_point_to_point_time(
                    locations[transporter.name], request.origin
                )
                time_to_dest = self._estimate_point_to_point_time(
                    request.origin, request.destination
                )
                completion_time = workloads[transporter.name] + time_to_origin + time_to_dest

                if completion_time < min_completion_time:
                    min_completion_time = completion_time
                    best_transporter = transporter

            # Assign to best transporter
            if best_transporter:
                plan[best_transporter.name].append(request)

                # Update state
                time_to_origin = self._estimate_point_to_point_time(
                    locations[best_transporter.name], request.origin
                )
                time_to_dest = self._estimate_point_to_point_time(
                    request.origin, request.destination
                )

                workloads[best_transporter.name] += time_to_origin + time_to_dest
                locations[best_transporter.name] = request.destination

        return plan

    def _solve_balanced(self):
        """
        Solve with focus on balanced workload among transporters.

        Returns:
            dict: Assignment plan
        """
        self.logger.debug("Solving with workload-balancing algorithm")
        plan = {t.name: [] for t in self.transporters}

        # Group requests by their geographical area (to minimize travel between clusters)
        geo_groups = self._group_requests_by_location()

        # Calculate estimated time for each request
        request_times = {}
        for request in self.requests:
            # Estimate straight travel time
            time_to_dest = self._estimate_point_to_point_time(request.origin, request.destination)
            request_times[request] = time_to_dest

        # Sort geo groups by total estimated time (descending)
        sorted_groups = sorted(
            geo_groups,
            key=lambda group: sum(request_times.get(r, 0) for r in group),
            reverse=True
        )

        # Pair groups with transporters to balance workload
        transporters_list = list(self.transporters)
        for i, group in enumerate(sorted_groups):
            # Assign this group to the transporter at the current round-robin position
            t_idx = i % len(transporters_list)
            transporter = transporters_list[t_idx]

            # Add all requests in this group to the transporter
            for request in group:
                plan[transporter.name].append(request)

        # Check workload balance and potentially rebalance
        workloads = {}
        for t_name, requests in plan.items():
            if not requests:
                workloads[t_name] = 0
                continue

            transporter = next(t for t in self.transporters if t.name == t_name)
            workloads[t_name] = self._calculate_transporter_workload(transporter, requests)

        # Try to balance if imbalance is significant
        if workloads:
            min_workload = min(workloads.values())
            max_workload = max(workloads.values())

            if max_workload > 2 * min_workload:  # Significant imbalance
                self._rebalance_workload(plan, workloads)

        return plan

    def _group_requests_by_location(self):
        """
        Group requests by geographical proximity.

        Returns:
            list: List of request groups
        """
        if not self.requests:
            return []

        # Use a simple clustering approach
        num_groups = min(max(3, len(self.transporters)), len(self.requests))

        # Calculate coordinates for each request (midpoint between origin and destination)
        request_coords = {}
        for request in self.requests:
            origin_coords = self._get_coordinates(request.origin)
            dest_coords = self._get_coordinates(request.destination)

            # Use midpoint as the request's position
            midpoint = ((origin_coords[0] + dest_coords[0]) / 2,
                        (origin_coords[1] + dest_coords[1]) / 2)

            request_coords[request] = midpoint

        # Initially put each request in its own group
        groups = [[r] for r in self.requests]

        # Merge groups until we have the desired number
        while len(groups) > num_groups:
            # Find the two closest groups
            min_dist = float('inf')
            closest_pair = (0, 1)

            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    dist = self._calculate_group_distance(groups[i], groups[j], request_coords)
                    if dist < min_dist:
                        min_dist = dist
                        closest_pair = (i, j)

            # Merge the closest groups
            i, j = closest_pair
            groups[i].extend(groups[j])
            groups.pop(j)

        return groups

    def _calculate_group_distance(self, group1, group2, coords_dict):
        """Calculate the average distance between two groups of requests."""
        total_dist = 0
        count = 0

        for r1 in group1:
            for r2 in group2:
                if r1 in coords_dict and r2 in coords_dict:
                    x1, y1 = coords_dict[r1]
                    x2, y2 = coords_dict[r2]
                    dist = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    total_dist += dist
                    count += 1

        return total_dist / max(1, count)

    def _get_coordinates(self, location):
        """Get coordinates for a location, or estimate if not available."""
        try:
            return self.graph.get_node_coordinates(location)
        except (AttributeError, KeyError):
            # Return origin or some default if coordinates not available
            return (0, 0)

    def _calculate_transporter_speeds(self):
        """Calculate relative speeds of different transporters."""
        speeds = {}

        # Use a standard path to estimate speed
        standard_origins = [t.current_location for t in self.transporters if t.current_location]

        if not standard_origins:
            return {t.name: 1.0 for t in self.transporters}

        # Use a common origin to compare speeds
        common_origin = standard_origins[0]

        # Find all departments for potential destinations
        departments = set()
        for r in self.requests:
            departments.add(r.origin)
            departments.add(r.destination)

        # If no departments, use default speeds
        if not departments:
            return {t.name: 1.0 for t in self.transporters}

        # Use a random sample of destinations
        sample_destinations = random.sample(list(departments), min(5, len(departments)))

        # For each transporter, estimate average speed
        for transporter in self.transporters:
            total_time = 0
            count = 0

            for dest in sample_destinations:
                time = self._estimate_point_to_point_time(common_origin, dest)
                if time > 0:
                    total_time += time
                    count += 1

            speeds[transporter.name] = total_time / max(1, count)

        # Normalize so that speeds are relative (higher is slower)
        if speeds:
            avg_speed = sum(speeds.values()) / len(speeds)
            speeds = {t: s / avg_speed for t, s in speeds.items()}

        return speeds

    def _calculate_transporter_workload(self, transporter, requests):
        """Calculate total workload for a transporter with given requests."""
        if not requests:
            return 0

        total_time = 0
        current_location = transporter.current_location

        for request in requests:
            # Time to origin
            origin_time = self._estimate_point_to_point_time(current_location, request.origin)

            # Time to destination
            dest_time = self._estimate_point_to_point_time(request.origin, request.destination)

            total_time += origin_time + dest_time
            current_location = request.destination

        return total_time

    def _rebalance_workload(self, plan, workloads):
        """
        Rebalance workload among transporters by moving requests.

        Args:
            plan: Current assignment plan
            workloads: Current workload estimates
        """
        # For significant imbalance, try moving requests from highest to lowest
        iterations = min(3, len(self.transporters) * 2)  # Limit iterations

        for _ in range(iterations):
            if not workloads:
                return

            # Find highest and lowest workload transporters
            max_workload = max(workloads.values())
            min_workload = min(workloads.values())

            if max_workload <= min_workload * 1.2:  # Within 20% is acceptable
                return

            max_transporter = [t for t, w in workloads.items() if w == max_workload][0]
            min_transporter = [t for t, w in workloads.items() if w == min_workload][0]

            # Find a request to move
            if max_transporter not in plan or not plan[max_transporter]:
                return

            # Get the shortest requests from max_transporter
            max_requests = plan[max_transporter]

            if not max_requests:
                return

            # Calculate request times for the overloaded transporter
            request_times = []

            t = next(t for t in self.transporters if t.name == max_transporter)
            location = t.current_location

            for i, request in enumerate(max_requests):
                # Time to origin then destination
                origin_time = self._estimate_point_to_point_time(location, request.origin)
                dest_time = self._estimate_point_to_point_time(request.origin, request.destination)

                total_time = origin_time + dest_time
                request_times.append((i, request, total_time))

                location = request.destination

            # Sort by time (shortest first) - these are easier to move
            request_times.sort(key=lambda x: x[2])

            # Try to move a request
            moved = False

            for _, request, req_time in request_times:
                # Check if moving this request improves balance
                new_max = max_workload - req_time
                new_min = min_workload + req_time  # Approximate

                # Only move if it actually improves balance
                if new_max >= new_min or new_max - new_min < max_workload - min_workload:
                    # Move the request
                    plan[max_transporter].remove(request)
                    if min_transporter not in plan:
                        plan[min_transporter] = []
                    plan[min_transporter].append(request)

                    # Update workloads (approximate)
                    workloads[max_transporter] = new_max
                    workloads[min_transporter] = new_min

                    moved = True
                    break

            if not moved:
                return  # No suitable request found

    def _estimate_point_to_point_time(self, start, end):
        """
        Estimate travel time between two points with caching.

        Args:
            start: Start location
            end: End location

        Returns:
            float: Estimated travel time
        """
        # Check cache first
        cache_key = f"{start}_{end}"
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

        try:
            if not self.transporters:
                return 0

            path, _ = self.transporters[0].pathfinder.dijkstra(start, end)

            if not path or len(path) < 2:
                return 0

            time = sum(self.graph.get_edge_weight(path[i], path[i + 1])
                       for i in range(len(path) - 1))

            # Cache the result
            self.path_cache[cache_key] = time

            return time
        except (IndexError, AttributeError, ValueError) as e:
            self.logger.debug(f"Error estimating travel time: {e}")
            return 10  # Default time if path calculation fails

    def _sort_requests_by_greedy_chain(self, transporter, requests):
        """Sort requests by a greedy chain to minimize travel time."""
        if not requests:
            return []

        remaining = deepcopy(requests)
        ordered = []
        current_location = transporter.current_location

        while remaining:
            # Find request whose origin is closest to current location
            next_request = min(
                remaining,
                key=lambda r: self._estimate_point_to_point_time(current_location, r.origin)
            )
            ordered.append(next_request)
            current_location = next_request.destination
            remaining.remove(next_request)

        return ordered

    def _log_performance(self):
        """Log detailed performance metrics."""
        self.logger.info(f"=== Genetic Algorithm Performance ===")
        self.logger.info(f"Total runtime: {self.total_time:.2f} seconds")
        self.logger.info(f"Generations run: {self.current_generation + 1} of {self.generations} max")
        self.logger.info(f"Best fitness: {self.best_fitness:.2f} at generation {self.best_generation}")
        self.logger.info(f"Final population size: {len(self.population)}")

        # Time distribution
        self.logger.info(f"Time breakdown:")
        self.logger.info(
            f"  Initialization: {self.initialization_time:.2f}s ({100 * self.initialization_time / max(0.001, self.total_time):.1f}%)")
        self.logger.info(
            f"  Evolution: {self.evolution_time:.2f}s ({100 * self.evolution_time / max(0.001, self.total_time):.1f}%)")
        self.logger.info(f"  Fitness evaluation: {self.fitness_eval_time:.2f}s")
        self.logger.info(f"  Selection: {self.selection_time:.2f}s")
        self.logger.info(f"  Crossover: {self.crossover_time:.2f}s")
        self.logger.info(f"  Mutation: {self.mutation_time:.2f}s")

        # Diversity statistics
        if self.diversity_history:
            self.logger.info(f"Final diversity: {self.diversity_history[-1]:.3f}")
            self.logger.info(f"Diversity range: {min(self.diversity_history):.3f} - {max(self.diversity_history):.3f}")

        # Improvement statistics
        if len(self.fitness_history) > 1:
            initial = self.fitness_history[0]
            final = self.fitness_history[-1]
            improvement = (initial - final) / initial if initial > 0 else 0
            self.logger.info(f"Overall improvement: {improvement:.1%}")

            # Calculate improvement rate
            generations = len(self.fitness_history)
            improvement_per_gen = improvement / max(1, generations - 1)
            self.logger.info(f"Avg improvement per generation: {improvement_per_gen:.3%}")

    def estimate_travel_time(self, transporter, request):
        """
        Estimate travel time for a transporter to complete a request.

        Args:
            transporter: Transporter object
            request: Request object

        Returns:
            float: Estimated travel time in seconds
        """
        # Calculate time from current location to request origin
        to_origin_time = self._estimate_point_to_point_time(
            transporter.current_location, request.origin
        )

        # Calculate time from origin to destination
        to_dest_time = self._estimate_point_to_point_time(
            request.origin, request.destination
        )

        return to_origin_time + to_dest_time