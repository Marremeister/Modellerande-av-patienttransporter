# ilp_mode.py
from enum import Enum

class ILPMode(Enum):
    MAKESPAN = "makespan"
    EQUAL_WORKLOAD = "equal_workload"
    URGENCY_FIRST = "urgency_first"
    CLUSTER_BASED = "cluster_based"  # New mode for cluster-based approach