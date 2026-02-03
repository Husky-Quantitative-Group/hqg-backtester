from abc import ABC
from ..models.request import BacktestRequest

class ExecutionOrchestrator(ABC):
    """
    Manages each individual pre-warmed execution container and their runtimes.
    Responsibilites include executing requests, managing the pool, and handling shutdown/cleanup.
    This should also communicate with the output validator, and should manage its response. See implementation
    within handlers.py for reference.
    """