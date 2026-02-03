from abc import ABC, abstractmethod
from .executor import RawExecutionResult


class OutputValidator(ABC):
    """
    Final security checkpoint. Ensures executor output
    is sane before metrics are computed.
    """

    @abstractmethod
    def validate(self, output: RawExecutionResult) -> RawExecutionResult:
        """
        Validate raw executor output (no NaN, positive prices, etc).

        Args:
            output: Raw output from executor

        Returns:
            Validated RawExecutionResult (same type, just sanity-checked)
        """
        pass