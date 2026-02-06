import cProfile
import pstats
import io
import pytest
from datetime import datetime

from src.models.request import BacktestRequest, ExecutionException
from src.models.execution import RawExecutionResult
from src.validation.analysis import StaticAnalyzer
from src.api.handlers import BacktestHandler
from src.validation.output_validator import OutputValidator
from tests.test_strategies.pytest_strategies import TestStrategies


def make_dashboard_request(
    strategy_code: str,
    start_date: datetime = datetime(2023, 1, 1),
    end_date: datetime = datetime(2024, 1, 1),
    initial_capital: float = 10000.0,
    commission: float = 0.001,
    slippage: float = 0.001,
    name: str = "Dashboard Backtest",
) -> BacktestRequest:
    """
    Simulate a real request from the dashboard.

    This mirrors what the frontend would send to /api/v1/backtest.
    """
    return BacktestRequest(
        strategy_code=strategy_code,
        name=name,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
    )


def make_valid_execution_result(
    final_value: float = 10500.0,
    final_cash: float = 500.0,
    num_trades: int = 5,
) -> RawExecutionResult:
    """Create a valid RawExecutionResult for mocking executor responses."""
    trades = [
        {
            "symbol": "AAPL",
            "price": 150.0,
            "amount": 10,
            "timestamp": "2023-06-01T10:00:00",
        }
        for _ in range(num_trades)
    ]
    equity_curve = {
        f"2023-{i:02d}-01T00:00:00": 10000.0 + (i * 50) for i in range(1, 13)
    }
    return RawExecutionResult(
        final_value=final_value,
        final_cash=final_cash,
        trades=trades,
        equity_curve=equity_curve,
        final_positions={"AAPL": 50.0},
    )


class TestValidationCorrectness:
    """
    Verify components enforce their expected constraints.

    """
    def test_static_analyzer_requires_strategy_class(self):
        request = make_dashboard_request(TestStrategies.MALICIOUS_NO_STRATEGY)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty()
        assert any("Strategy" in e for e in request.errors.errors)

    def test_static_analyzer_validates_allowed_nodes(self):
        request = make_dashboard_request(TestStrategies.VALID_BUYHOLD)
        result = StaticAnalyzer.analyze(request)

        assert (
            result.errors.is_empty()
        ), f"Valid strategy failed: {result.errors.errors}"

    def test_output_validator_rejects_nan_values(self):
        validator = OutputValidator()
        bad_result = RawExecutionResult(
            final_value=float("nan"),
            final_cash=1000.0,
            equity_curve={"2023-01-01": 10000.0},
        )

        with pytest.raises(ExecutionException) as exc_info:
            validator.validate(bad_result)
        assert "Invalid final_value" in str(exc_info.value)

        with pytest.raises(ExecutionException) as exc_info:
            validator.validate(bad_result)
        assert "non-positive price" in str(exc_info.value)


class TestValidationSecurity:
    """
    Verify malicious requests are rejected at the appropriate pipeline stage.
    """

    def test_blocks_os_import_at_static_analyzer(self):
        """
        Import os module for system command execution.
        Expected failure: StaticAnalyzer._validate_imports
        """
        request = make_dashboard_request(TestStrategies.MALICIOUS_OS_IMPORT)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "os import should be blocked"
        assert any("Import" in e and "not allowed" in e for e in request.errors.errors)

    def test_blocks_subprocess_import_at_static_analyzer(self):
        """
        Import subprocess for arbitrary command execution.
        Expected failure: StaticAnalyzer._validate_imports
        """
        request = make_dashboard_request(TestStrategies.MALICIOUS_SUBPROCESS_IMPORT)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "subprocess import should be blocked"
        assert any("Import" in e and "not allowed" in e for e in request.errors.errors)

    def test_blocks_eval_at_static_analyzer(self):
        """
        Use eval() to execute arbitrary code strings.
        Expected failure: StaticAnalyzer._validate_builtins
        """
        request = make_dashboard_request(TestStrategies.MALICIOUS_EVAL)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "eval() should be blocked"
        assert any("eval" in e and "forbidden" in e for e in request.errors.errors)

    def test_blocks_open_at_static_analyzer(self):
        """
        Use open() to read sensitive files.
        Expected failure: StaticAnalyzer._validate_builtins
        """
        request = make_dashboard_request(TestStrategies.MALICIOUS_OPEN_FILE)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "open() should be blocked"
        assert any("open" in e and "forbidden" in e for e in request.errors.errors)

    def test_blocks_globals_access_at_static_analyzer(self):
        """
        Access __globals__ to escape sandbox.
        Expected failure: StaticAnalyzer._validate_attributes
        """
        request = make_dashboard_request(TestStrategies.MALICIOUS_GLOBALS_ACCESS)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "__globals__ access should be blocked"
        assert any(
            "__globals__" in e and "forbidden" in e for e in request.errors.errors
        )

    def test_blocks_class_escape_at_static_analyzer(self):
        """
        Use __class__.__bases__ for type confusion sandbox escape.
        Expected failure: StaticAnalyzer._validate_attributes
        """
        request = make_dashboard_request(TestStrategies.MALICIOUS_CLASS_ESCAPE)
        StaticAnalyzer.analyze(request)

        assert (
            not request.errors.is_empty()
        ), "__class__/__bases__ access should be blocked"
        # Should catch __class__ or __bases__
        errors_str = " ".join(request.errors.errors)
        assert "__class__" in errors_str or "__bases__" in errors_str


@pytest.mark.integration
class TestValidationIntegration:
    """
    End-to-end pipeline tests with REAL infrastructure.

    Requirements:
    - Docker running with hqg-backtester-sandbox image built
    - Network access for Yahoo Finance API
    - Run with: pytest tests/test_validation.py -v -m integration
    """

    @pytest.mark.asyncio
    async def test_valid_strategy_full_pipeline(self):
        """
        Real dashboard request through the full pipeline.

        Tests: Static analysis -> Strategy loading -> Market data fetch ->
               Docker execution -> Output validation
        """
        handler = BacktestHandler()
        request = make_dashboard_request(
            strategy_code=TestStrategies.VALID_BUYHOLD,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=10000.0,
        )

        result = await handler.handle_backtest(request)

        # Verify we got real results
        assert result.metrics is not None
        assert result.equity_stats is not None
        assert result.parameters.initial_capital == 10000.0

    @pytest.mark.asyncio
    async def test_malicious_os_import_rejected(self):
        """
        Malicious code with os import should be rejected at static analysis.
        Should never reach Docker execution.
        """
        handler = BacktestHandler()
        request = make_dashboard_request(TestStrategies.MALICIOUS_OS_IMPORT)

        with pytest.raises(Exception) as exc_info:
            await handler.handle_backtest(request)

        # Should fail with validation error, not execution error
        assert "Import" in str(exc_info.value) or "analysis" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_malicious_eval_rejected(self):
        """
        Code using eval() should be rejected at static analysis.
        """
        handler = BacktestHandler()
        request = make_dashboard_request(TestStrategies.MALICIOUS_EVAL)

        with pytest.raises(Exception) as exc_info:
            await handler.handle_backtest(request)

        assert "eval" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_malicious_file_access_rejected(self):
        """
        Code using open() should be rejected at static analysis.
        """
        handler = BacktestHandler()
        request = make_dashboard_request(TestStrategies.MALICIOUS_OPEN_FILE)

        with pytest.raises(Exception) as exc_info:
            await handler.handle_backtest(request)

        assert "open" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_syntax_error_rejected(self):
        """
        Code with syntax errors should fail at static analysis.
        """
        bad_syntax = """
from hqg_algorithms import Strategy

class BrokenStrategy(Strategy
    def universe(self):
        return ["AAPL"]
"""
        handler = BacktestHandler()
        request = make_dashboard_request(bad_syntax)

        with pytest.raises(Exception) as exc_info:
            await handler.handle_backtest(request)

        assert "syntax" in str(exc_info.value).lower()

async def ProfileTests():
    """
    Performance Profiling
    """
    profiler = cProfile.Profile()

    test_cases = [TestStrategies.VALID_BUYHOLD, TestStrategies.VALID_SMA, TestStrategies.VALID_MULTIASSET]

    print(f"\n{'='*70}")
    print(f"Validation Pipeline Profiling")
    print(f"{'='*70}")
    print(f"Running {len(test_cases)} test cases\n")

    profiler.enable()
    handler = BacktestHandler()
    for code in test_cases:
        request = make_dashboard_request(code)
        br = await handler.handle_backtest(request=request)
    profiler.disable()
    print(br.parameters, br.equity_stats, br.metrics)
    # Print summary stats
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(20)

    print(stream.getvalue())

    print(f"\n{'='*70}")
    print("Per-Test Timing Summary")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    """
    Run profiling when executed directly.

    Usage:
        python -m tests/test_validation.py

    For pytest:
        pytest tests/test_validation.py -v
    """
    import asyncio

    async def main():
        await ProfileTests()

    asyncio.run(main())
