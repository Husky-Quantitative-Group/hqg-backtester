from abc import ABC, abstractmethod
from ..models.response import BacktestResponse, BacktestResult


class OutputValidator(ABC):
    """
    This is the final security checkpoint. It ensures executor output
    conforms to expected client-side schema.
    """

    @abstractmethod
    def validate(self, output: ExecutionResult) -> BacktestResult | BacktestResponse: #NOTE: I think either or can be used here
        """
        Validate raw executor output, prep for response back to client.

        Args:
            output: Raw output from executor

        Returns:
            Validated response model
        """
        pass