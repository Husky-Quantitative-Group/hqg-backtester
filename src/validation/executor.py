# executor.py
from abc import ABC, abstractmethod

class Executor(ABC):
    """
    Isolated execution environment for running validated user strategies.
    """

    @abstractmethod
    def execute(self, payload: ExecutionPayload, config: ExecutorConfig) -> RawExecutionResult: #NOTE: These models can be replaced with anything or implemented
        """
        Execute a strategy within the isolated environment.

        Args:
            payload: The execution payload containing code and market data
            config: Resource limits and timeout configuration

        Returns:
            Raw execution result (must be validated by OutputValidator before use)
        """
        pass