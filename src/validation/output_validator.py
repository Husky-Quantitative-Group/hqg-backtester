import math
import logging
from .executor import RawExecutionResult

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    Final security checkpoint. Ensures executor output
    is sane before metrics are computed.
    """

    def validate(self, output: RawExecutionResult) -> RawExecutionResult:
        """
        Validate raw executor output (no NaN, reasonable values, etc).

        Raises ValueError if output is fundamentally broken.
        Returns the same RawExecutionResult if valid.
        """
        if output.errors:
            logger.warning(f"Executor returned errors: {output.errors}")
            raise ValueError(f"Execution failed: {'; '.join(output.errors)}")

        # Final value must be a real number
        if math.isnan(output.final_value) or math.isinf(output.final_value):
            raise ValueError(f"Invalid final_value: {output.final_value}")

        if output.final_value < 0:
            raise ValueError(f"Negative final portfolio value: {output.final_value}")

        # Equity curve check
        for ts, val in output.equity_curve.items():
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Invalid equity curve value at {ts}: {val}")

        # Trade check
        for trade in output.trades:
            price = trade.get("price", 0)
            amount = trade.get("amount", 0)
            if price <= 0:
                raise ValueError(f"Trade with non-positive price: {price}")
            if amount <= 0:
                raise ValueError(f"Trade with non-positive amount: {amount}")

        # Must have at least some equity curve data
        if not output.equity_curve:
            raise ValueError("Empty equity curve — execution produced no data")

        return output
