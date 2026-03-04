import asyncio
import cProfile
import pstats
import io
import random
import time
import pytest
import httpx
from datetime import datetime
from pathlib import Path
from src.models.request import BacktestRequest
from src.execution.analysis import StaticAnalyzer
from src.api.handlers import BacktestHandler
from src.api.server import app
from tests.test_strategies.pytest_strategies import TestStrategies

_STRATS_DIR = Path(__file__).parent / "test_strategies" / "strats"
_STRAT_FILES = sorted(_STRATS_DIR.glob("*.py"))


def _random_strategy() -> str:
    """Return the source code of a randomly selected strategy from strats/."""
    return random.choice(_STRAT_FILES).read_text()


def make_request(
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


@pytest.mark.integration
class TestCorrectness:
    """
    Verify components enforce their expected constraints.
    """
    def test_static_analyzer_requires_strategy_class(self):
        request = make_request(TestStrategies.MALICIOUS_NO_STRATEGY)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty()
        assert any("Strategy" in e for e in request.errors.errors)

    def test_static_analyzer_validates_allowed_nodes(self):
        request = make_request(TestStrategies.VALID_BUYHOLD)
        result = StaticAnalyzer.analyze(request)

        assert (
            result.errors.is_empty()
        ), f"Valid strategy failed: {result.errors.errors}"
        
    @pytest.mark.asyncio
    async def test_buyhold_strategy_executes(self):
        handler = BacktestHandler()
        request = make_request(
            strategy_code=TestStrategies.VALID_BUYHOLD,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=10000.0,
        )

        result = await handler.run_backtest(request)

        assert result.metrics is not None
        assert result.equity_stats is not None
        assert result.parameters.starting_equity == 10000.0
        assert len(result.candles) > 0, "Should have equity curve data"

    @pytest.mark.asyncio
    async def test_sma_strategy_executes(self):
        handler = BacktestHandler()
        request = make_request(
            strategy_code=TestStrategies.VALID_SMA,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=50000.0,
        )

        result = await handler.run_backtest(request)

        assert result.metrics is not None
        assert result.metrics.total_orders >= 0, "SMA strategy may generate trades"
        assert result.parameters.starting_equity == 50000.0

    @pytest.mark.asyncio
    async def test_multiasset_strategy_executes(self):
        handler = BacktestHandler()
        request = make_request(
            strategy_code=TestStrategies.VALID_MULTIASSET,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=100000.0,
        )

        result = await handler.run_backtest(request)

        assert result.metrics is not None
        assert result.equity_stats is not None
        assert len(result.orders) > 0, "Multi-asset strategy should generate orders"

    @pytest.mark.asyncio
    async def test_commission_affects_results(self):
        handler = BacktestHandler()
        request_zero = make_request(
            strategy_code=TestStrategies.VALID_BUYHOLD,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            commission=0.0,
        )
        result_zero = await handler.run_backtest(request_zero)

        request_high = make_request(
            strategy_code=TestStrategies.VALID_BUYHOLD,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            commission=0.01,
        )
        result_high = await handler.run_backtest(request_high)

        # Higher commission should result in lower or equal final equity
        assert result_high.equity_stats.fees >= result_zero.equity_stats.fees

    @pytest.mark.asyncio
    async def test_equity_candles_have_ohlc(self):
        handler = BacktestHandler()
        request = make_request(
            strategy_code=TestStrategies.VALID_BUYHOLD,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
        )

        result = await handler.run_backtest(request)

        assert len(result.candles) > 0
        candle = result.candles[0]
        assert hasattr(candle, 'time')
        assert hasattr(candle, 'open')
        assert hasattr(candle, 'high')
        assert hasattr(candle, 'low')
        assert hasattr(candle, 'close')
        # OHLC invariant: low <= open,close <= high
        assert candle.low <= candle.open <= candle.high
        assert candle.low <= candle.close <= candle.high
        
    @pytest.mark.asyncio
    async def test_runtime_division_by_zero(self):
        """Strategy with division by zero should fail gracefully at runtime."""
        runtime_error_strategy = '''
from hqg_algorithms import Strategy

class DivZeroStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def on_data(self, data, portfolio):
        x = 1 / 0  # Runtime error
        return {"AAPL": 1.0}
'''
        handler = BacktestHandler()
        request = make_request(
            strategy_code=runtime_error_strategy,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 2, 1),
        )

        with pytest.raises(Exception) as exc_info:
            await handler.run_backtest(request)

        assert "division" in str(exc_info.value).lower() or "zero" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_runtime_invalid_symbol(self):
        """Strategy requesting invalid symbol should handle gracefully."""
        invalid_symbol_strategy = '''
from hqg_algorithms import Strategy

class InvalidSymbolStrategy(Strategy):
    def universe(self):
        return ["NOTAREALSYMBOL12345"]

    def on_data(self, data, portfolio):
        return {"NOTAREALSYMBOL12345": 1.0}
'''
        handler = BacktestHandler()
        request = make_request(
            strategy_code=invalid_symbol_strategy,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 2, 1),
        )
        with pytest.raises(Exception):
            await handler.run_backtest(request)
    
    @pytest.mark.asyncio
    async def test_runtime_invalid_weight(self):
        """Strategy returning weights > 1.0 should fail at execution."""
        overweight_strategy = '''
from hqg_algorithms import Strategy

class OverweightStrategy(Strategy):
    def universe(self):
        return ["AAPL", "MSFT"]

    def on_data(self, data, portfolio):
        return {"AAPL": 0.8, "MSFT": 0.8}  # Sum > 1.0
'''
        handler = BacktestHandler()
        request = make_request(
            strategy_code=overweight_strategy,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 2, 1),
        )

        with pytest.raises(Exception) as exc_info:
            await handler.run_backtest(request)

        assert "weight" in str(exc_info.value).lower() or "1.0" in str(exc_info.value)

class TestSecurity:
    """
    Verify malicious requests are rejected at the appropriate pipeline stage.
    """

    def test_blocks_os_import_at_static_analyzer(self):
        """
        Import os module for system command execution.
        Expected failure: StaticAnalyzer._validate_imports
        """
        request = make_request(TestStrategies.MALICIOUS_OS_IMPORT)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "os import should be blocked"
        assert any("Import" in e and "not allowed" in e for e in request.errors.errors)

    def test_blocks_subprocess_import_at_static_analyzer(self):
        """
        Import subprocess for arbitrary command execution.
        Expected failure: StaticAnalyzer._validate_imports
        """
        request = make_request(TestStrategies.MALICIOUS_SUBPROCESS_IMPORT)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "subprocess import should be blocked"
        assert any("Import" in e and "not allowed" in e for e in request.errors.errors)

    def test_blocks_eval_at_static_analyzer(self):
        """
        Use eval() to execute arbitrary code strings.
        Expected failure: StaticAnalyzer._validate_builtins
        """
        request = make_request(TestStrategies.MALICIOUS_EVAL)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "eval() should be blocked"
        assert any("eval" in e and "forbidden" in e for e in request.errors.errors)

    def test_blocks_open_at_static_analyzer(self):
        """
        Use open() to read sensitive files.
        Expected failure: StaticAnalyzer._validate_builtins
        """
        request = make_request(TestStrategies.MALICIOUS_OPEN_FILE)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "open() should be blocked"
        assert any("open" in e and "forbidden" in e for e in request.errors.errors)

    def test_blocks_globals_access_at_static_analyzer(self):
        """
        Access __globals__ to escape sandbox.
        Expected failure: StaticAnalyzer._validate_attributes
        """
        request = make_request(TestStrategies.MALICIOUS_GLOBALS_ACCESS)
        StaticAnalyzer.analyze(request)

        assert not request.errors.is_empty(), "__globals__ access should be blocked"
        assert any(
            "__globals__" in e and "forbidden" in e for e in request.errors.errors
        )

@pytest.mark.integration
class TestIntegration:
    """
    End-to-end pipeline tests with real infrastructure.

    These tests verify the full execution path:
    Static analysis -> Strategy loading -> Market data fetch -> Docker execution -> Output validation

    Run with: pytest tests/test_validation.py -v -m integration
    """

    @pytest.mark.asyncio
    @classmethod
    async def test_mean_variance_strategy(self):
        """Mean-variance optimization strategy (strategy_20)."""
        strategy_code = (_STRATS_DIR / "strategy_20_mean_variance_opt_monthly.py").read_text()

        handler = BacktestHandler()
        request = make_request(
            strategy_code=strategy_code,
            start_date=datetime(2019, 1, 1),
            end_date=datetime(2025, 1, 1),
            initial_capital=100000.0,
        )

        result = await handler.run_backtest(request)

        assert result.metrics is not None
        assert result.equity_stats is not None
        assert len(result.candles) > 0

    @pytest.mark.asyncio
    @classmethod
    async def test_sma_crossover_strategy(self):
        """SMA crossover strategy (strategy_02)."""
        strategy_code = (_STRATS_DIR / "strategy_02_sma_crossover_qqq_weekly.py").read_text()

        handler = BacktestHandler()
        request = make_request(
            strategy_code=strategy_code,
            start_date=datetime(2015, 1, 1),
            end_date=datetime(2025, 1, 1),
            initial_capital=100000.0,
        )

        result = await handler.run_backtest(request)

        assert result.metrics is not None
        assert result.equity_stats is not None
        assert len(result.candles) > 0

@pytest.mark.integration
class TestLoad:
    """
    Simulate N concurrent users submitting backtest requests simultaneously.
    Each request uses a randomly selected strategy for payload diversity.
    """

    N = 5

    @pytest.mark.asyncio
    async def test_concurrent_backtest_requests(self):
        payloads = [
            {
                "strategy_code": _random_strategy(),
                "name": f"Load Test {i}",
                "start_date": "2019-01-01T00:00:00",
                "end_date": "2025-01-01T00:00:00",
                "initial_capital": 100000.0,
                "commission": 0.001,
                "slippage": 0.001,
            }
            for i in range(self.N)
        ]

        async def timed_request(client, request_id, payload):
            start = time.perf_counter()
            response = await client.post(
                "/api/v1/backtest", json=payload, timeout=600.0
            )
            elapsed = time.perf_counter() - start
            return request_id, response, elapsed

        _start = time.perf_counter()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            tasks = [timed_request(client, i, payloads[i]) for i in range(self.N)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        _elapsed = time.perf_counter() - _start

        for request_id, response, elapsed in results:
            assert response.status_code == 200, (
                f"Request {request_id} failed with {response.status_code}: {response.text}"
            )

        for request_id, response, elapsed in results:
            data = response.json()
            assert "metrics" in data
            assert "equity_stats" in data
            assert "candles" in data
            assert "orders" in data
            metrics = data["metrics"]
            assert 0.0 <= metrics["max_drawdown"] <= 1.0, (
                f"Request {request_id}: max_drawdown out of range: {metrics['max_drawdown']}"
            )
            assert 0.0 <= metrics["win_rate"] <= 1.0, (
                f"Request {request_id}: win_rate out of range: {metrics['win_rate']}"
            )

        print(f"Load Test: {self.N} requests completed in {_elapsed:.2f}s")
@pytest.mark.integration
class TestStress:
    """
    Simulate N concurrent users submitting backtest requests simultaneously.
    Each request uses a randomly selected strategy for payload diversity.
    """

    N = 50

    @pytest.mark.asyncio
    async def test_concurrent_backtest_requests(self):
        payloads = [
            {
                "strategy_code": _random_strategy(),
                "name": f"Stress Test {i}",
                "start_date": "2019-01-01T00:00:00",
                "end_date": "2025-01-01T00:00:00",
                "initial_capital": 100000.0,
                "commission": 0.001,
                "slippage": 0.001,
            }
            for i in range(self.N)
        ]

        async def timed_request(client, request_id, payload):
            start = time.perf_counter()
            response = await client.post(
                "/api/v1/backtest", json=payload, timeout=600.0
            )
            elapsed = time.perf_counter() - start
            return request_id, response, elapsed

        _start = time.perf_counter()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            tasks = [timed_request(client, i, payloads[i]) for i in range(self.N)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        _elapsed = time.perf_counter() - _start

        for request_id, response, elapsed in results:
            assert response.status_code == 200, (
                f"Request {request_id} failed with {response.status_code}: {response.text}"
            )

        for request_id, response, elapsed in results:
            data = response.json()
            assert "metrics" in data
            assert "equity_stats" in data
            assert "candles" in data
            assert "orders" in data
            metrics = data["metrics"]
            assert 0.0 <= metrics["max_drawdown"] <= 1.0, (
                f"Request {request_id}: max_drawdown out of range: {metrics['max_drawdown']}"
            )
            assert 0.0 <= metrics["win_rate"] <= 1.0, (
                f"Request {request_id}: win_rate out of range: {metrics['win_rate']}"
            )

        print(f"Stress Test: {self.N} requests completed in {_elapsed:.2f}s")


async def ProfileTests():
    """
    Performance Profiling
    """
    profiler = cProfile.Profile()

    print(f"\n{'='*70}")
    print(f"Validation Pipeline Profiling")
    print(f"{'='*70}")

    # Profile basic small-scale test cases
    # profiler.enable()
    # handler = BacktestHandler()
    # for code in test_cases:
    #     request = make_request(code)
    #     br = await handler.run_backtest(request=request)
    # profiler.disable()
    # print(br.parameters, br.equity_stats, br.metrics)
    
    # Profile integration test
    profiler.enable()
    await TestIntegration().test_sma_crossover_strategy()
    profiler.disable()

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
        docker build -t hqg-backtester .
        docker build -t hqg-backtester-sandbox .
        python -m tests.test_execution
        (PROFILE): HQG_PROFILE=1 python -m tests.test_execution

    For pytest:
        pytest tests/test_execution.py -v
    """
    import asyncio

    async def main():
        await ProfileTests()

    asyncio.run(main())
