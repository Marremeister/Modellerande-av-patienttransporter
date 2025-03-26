# strategy_registry.py
from Model.Assignment_strategies.Random.random_assignment_strategy import RandomAssignmentStrategy
from Model.Assignment_strategies.ILP.ilp_optimizer_strategy import ILPOptimizerStrategy
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode
from Model.Assignment_strategies.Genetic_algorithms.genetic_algorithm_strategy import GeneticAlgorithmStrategy

STRATEGY_REGISTRY = {
    "Random": RandomAssignmentStrategy,
    "ILP: Makespan": lambda: ILPOptimizerStrategy(ILPMode.MAKESPAN),
    "ILP: Equal Workload": lambda: ILPOptimizerStrategy(ILPMode.EQUAL_WORKLOAD),
    "ILP: Urgency First": lambda: ILPOptimizerStrategy(ILPMode.URGENCY_FIRST),
    "ILP: Cluster-Based": lambda: ILPOptimizerStrategy(ILPMode.CLUSTER_BASED, num_clusters=7),
    "Genetic Algorithm": lambda: GeneticAlgorithmStrategy(population_size=50, generations=50)
}