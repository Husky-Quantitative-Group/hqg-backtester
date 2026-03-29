import math
import logging
from ..models.execution import RawExecutionResult
from ..models.request import BacktestRequestError, ExecutionException

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    Final security checkpoint. Ensures executor output
    is sane before metrics are computed.
    """

    def validate(self, output: RawExecutionResult) -> RawExecutionResult:
        """
        Validate raw executor output (no NaN, reasonable values, etc).

        Accumulates errors using BacktestRequestError pattern.
        Raises ExecutionException if any validation errors are found.
        Returns the same RawExecutionResult if valid.
        """
        errors = BacktestRequestError()

        # Final value must be a real number
        if math.isnan(output.final_value) or math.isinf(output.final_value):
            errors.add(f"Invalid final_value: {output.final_value}")

        if output.final_value < 0:
            errors.add(f"Negative final portfolio value: {output.final_value}")

        # Equity curve check
        for ts, val in output.equity_curve.items():
            if math.isnan(val) or math.isinf(val):
                errors.add(f"Invalid equity curve value at {ts}: {val}")

        # Order check
        for order in output.orders:
            price = order.get("price", 0)
            shares = order.get("shares", 0)
            if price <= 0:
                errors.add(f"Order with non-positive price: {price}")
            if shares <= 0:
                errors.add(f"Order with non-positive shares: {shares}")

        # Must have at least some equity curve data
        if not output.equity_curve:
            errors.add("Empty equity curve — execution produced no data")

        if not errors.is_empty():
            raise ExecutionException(errors)

        return output
