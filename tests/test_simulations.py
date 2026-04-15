import asyncio
import cProfile
import pstats
import io
import pytest
import httpx
from pathlib import Path
from src.api.server import app
from src.models.jobs import JobStatus
from src.scheduler.scheduler import scheduler

_STRATS_DIR = Path(__file__).parent / "test_strategies" / "strats"
_SMA_CONFIG = (_STRATS_DIR / "strategy_21_sma_config_weekly.py").read_text()
_MOMENTUM_CONFIG = (_STRATS_DIR / "strategy_22_momentum_config_daily.py").read_text()


def make_payload(
    strategy_code: str,
    config_params: dict,
    start_date: str = "2023-01-01T00:00:00",
    end_date: str = "2024-01-01T00:00:00",
    initial_capital: float = 10000.0,
) -> dict:
    """
    Simulate a real simulation request from the dashboard.

    Mirrors what the frontend would send to /api/v1/backtest.
    config_params carries the full sweep spec (simulation type + objective + params space).
    """
    return {
        "strategy_code": strategy_code,
        "name": "Simulation Test",
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "config_params": config_params,
    }


async def submit_and_poll(client: httpx.AsyncClient, payload: dict) -> dict:
    response = await client.post("/api/v1/backtest", json=payload, timeout=600.0)
    assert response.status_code == 202, f"Submit failed: {response.text}"
    job_id = response.json()["job_id"]

    scheduler_task = asyncio.create_task(scheduler.run())
    try:
        while True:
            poll = await client.get(f"/api/v1/backtest/{job_id}", timeout=10.0)
            assert poll.status_code == 200, f"Poll failed ({poll.status_code}): {poll.text}"
            data = poll.json()
            if data["status"] == JobStatus.COMPLETED:
                return data["result"]
            if data["status"] == JobStatus.FAILED:
                raise AssertionError(f"Job {job_id} failed: {data.get('error')}")
            await asyncio.sleep(3)
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


def print_runs(result: dict, objective: str) -> None:
    for run in result["runs"]:
        score = run["result"]["metrics"][objective]
        print(f"  params={run['config_params']}  {objective}={score:.4f}")
    print(f"Best: params={result['best_params']}  {objective}={result['best_metrics'][objective]:.4f}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestGridSearch:
    async def test_sma_grid_search(self):
        config_params = {
            "simulation": "grid",
            "objective": "sharpe",
            "params": {
                "fast_period": [5, 10],
                "slow_period": [20, 30],
            },
        }
        payload = make_payload(strategy_code=_SMA_CONFIG, config_params=config_params)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            result = await submit_and_poll(client, payload)

        print_runs(result, config_params["objective"])

        assert result["simulation_type"] == "grid"
        assert result["total_runs"] == 4  # 2 fast x 2 slow
        assert "fast_period" in result["best_params"]
        assert "slow_period" in result["best_params"]
        assert result["best_metrics"] is not None

    async def test_momentum_grid_search(self):
        config_params = {
            "simulation": "grid",
            "objective": "sharpe",
            "params": {
                "lookback": [10, 20, 40],
            },
        }
        payload = make_payload(strategy_code=_MOMENTUM_CONFIG, config_params=config_params)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            result = await submit_and_poll(client, payload)

        print_runs(result, config_params["objective"])

        assert result["simulation_type"] == "grid"
        assert result["total_runs"] == 3
        assert "lookback" in result["best_params"]
        assert result["best_metrics"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestBayesianSearch:
    async def test_sma_bayesian_search(self):
        config_params = {
            "simulation": "bayes",
            "objective": "sharpe",
            "n_initial": 3,
            "n_iterations": 2,
            "params": {
                "fast_period": {"type": "int", "min": 5, "max": 15},
                "slow_period": {"type": "int", "min": 20, "max": 40},
            },
        }
        payload = make_payload(strategy_code=_SMA_CONFIG, config_params=config_params)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            result = await submit_and_poll(client, payload)

        print_runs(result, config_params["objective"])

        assert result["simulation_type"] == "bayes"
        assert result["total_runs"] <= 5  # 3 initial + 2 iterations
        assert "fast_period" in result["best_params"]
        assert "slow_period" in result["best_params"]
        assert result["best_metrics"] is not None

    async def test_momentum_bayesian_search(self):
        config_params = {
            "simulation": "bayes",
            "objective": "sharpe",
            "n_initial": 3,
            "n_iterations": 2,
            "params": {
                "lookback": {"type": "int", "min": 10, "max": 50},
            }
        }
        payload = make_payload(strategy_code=_MOMENTUM_CONFIG, config_params=config_params)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            result = await submit_and_poll(client, payload)

        print_runs(result, config_params["objective"])

        assert result["simulation_type"] == "bayes"
        assert result["total_runs"] <= 5
        assert "lookback" in result["best_params"]
        assert result["best_metrics"] is not None


async def ProfileSimulations():
    """
    Performance Profiling
    """
    profiler = cProfile.Profile()

    print(f"\n{'='*70}")
    print("Simulation Pipeline Profiling")
    print(f"{'='*70}")

    profiler.enable()
    await TestBayesianSearch().test_momentum_bayesian_search()
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
        python -m tests.test_simulations
        (PROFILE): HQG_PROFILE=1 python -m tests.test_simulations

    For pytest:
        pytest tests/test_simulations.py -v -m integration
    """

    async def main():
        await ProfileSimulations()

    asyncio.run(main())
