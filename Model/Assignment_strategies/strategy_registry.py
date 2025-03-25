# strategy_registry.py
# strategy_registry.py
from Model.Assignment_strategies.Random.random_assignment_strategy import RandomAssignmentStrategy
from Model.Assignment_strategies.ILP.ilp_optimizer_strategy import ILPOptimizerStrategy
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode

STRATEGY_REGISTRY = {
    "Random": RandomAssignmentStrategy,
    "ILP: Makespan": lambda: ILPOptimizerStrategy(ILPMode.MAKESPAN),
    "ILP: Equal Workload": lambda: ILPOptimizerStrategy(ILPMode.EQUAL_WORKLOAD),
    "ILP: Urgency First": lambda: ILPOptimizerStrategy(ILPMode.URGENCY_FIRST)
}

