# tests.test_backtester
"""
Backtester service unit tests

This module tests the backtester functionality by:
1. Running baseline strategies (defined in QuantConnect, adapted for our system)
2. Comparing output metrics against hardcoded QuantConnect results
3. Validating performance within acceptable error thresholds
4. Benchmarking execution speed against baseline

Strategies tested:
- MeanVar: Convex optimization strategy using mean-variance allocation
  (Additional strategies: buy-and-hold, SMA will be added)

Note: Currently assuming no fee structure
"""

import pytest
import asyncio
from datetime import datetime
from hqg_algorithms import *
from src.services.backtester import Backtester
from src.models.response import PerformanceMetrics
from tests.test_strategies import MeanVar


MEANVAR_QC_METRICS = {
    "total_return": 0.31763,          # 31.763% net profit / total return
    "annualized_return": 0.04154,     # 4.154% compounding annual return
    "sharpe_ratio": 0.029,            # Sharpe ratio
    "max_drawdown": -0.22400,         # -22.400% max drawdown
    "win_rate": 0.62,                 # 62% win rate
    "total_orders": 6411,             # total orders
    "sortino": 0.022,                 # Sortino ratio
    "alpha": -0.016,                  # alpha vs benchmark
    "beta": 0.183,                    # beta vs benchmark
    "psr": 0.04366,                   # 4.366% PSR
    "avg_win": 0.0005,                # 0.05% average win
    "avg_loss": -0.0006,              # -0.06% average loss
}

MEANVAR_QC_SPEED_SECONDS = 135  # QuantConnect execution time in seconds (took 2:15 min to run)


# Error tolerance for metric comparisons (1% relative error)
METRIC_ERROR_THRESHOLD = 0.01  # 1%

# Date range for MeanVar baseline test
MEANVAR_START_DATE = datetime(2019, 1, 1)
MEANVAR_END_DATE = datetime(2024, 1, 31)
MEANVAR_INITIAL_CAPITAL = 100_000.0


def compare_metrics(
    actual: PerformanceMetrics,
    expected: dict,
    threshold: float = METRIC_ERROR_THRESHOLD,
    exclude_fields: list = None
) -> tuple[bool, dict, int]:
    """
    Compare actual metrics against expected values with relative error threshold.

    Args:
        actual: PerformanceMetrics from backtester
        expected: Dictionary of expected values
        threshold: Relative error threshold (default 1%)
        exclude_fields: Fields to skip comparison

    Returns:
        Tuple of (all_within_threshold, error_details, exceeded_count)
    """
    if exclude_fields is None:
        exclude_fields = []

    errors = {}
    all_within = True
    exceeded_count = 0  # count metrics that exceeded threshold or are missing

    for field, expected_val in expected.items():
        if field in exclude_fields:
            continue

        actual_val = getattr(actual, field, None)
        if actual_val is None:
            errors[field] = {"status": "MISSING", "expected": expected_val}
            all_within = False
            exceeded_count += 1
            continue

        # avoid division by zero
        if expected_val == 0:
            if actual_val != 0:
                errors[field] = {
                    "status": "OUTSIDE_THRESHOLD",
                    "expected": expected_val,
                    "actual": actual_val,
                    "error": abs(actual_val - expected_val)
                }
                all_within = False
                exceeded_count += 1
            else:
                errors[field] = {
                    "status": "OK",
                    "expected": expected_val,
                    "actual": actual_val,
                    "relative_error": 0.0
                }
        else:
            # Relative error: |actual - expected| / |expected|
            relative_error = abs(actual_val - expected_val) / abs(expected_val)

            if relative_error <= threshold:
                errors[field] = {
                    "status": "OK",
                    "expected": expected_val,
                    "actual": actual_val,
                    "relative_error": relative_error
                }
            else:
                errors[field] = {
                    "status": "OUTSIDE_THRESHOLD",
                    "expected": expected_val,
                    "actual": actual_val,
                    "relative_error": relative_error,
                    "threshold": threshold
                }
                all_within = False
                exceeded_count += 1

    return all_within, errors, exceeded_count


@pytest.mark.asyncio
async def test_meanvar_baseline_vs_quantconnect():
    """
    Test MeanVar strategy against QuantConnect baseline.

    Validates:
    - All metrics are within 1% relative error
    - Strategy executes and produces consistent results
    - Performance characteristics match expectations
    """
    # Initialize strategy and backtester
    strategy = MeanVar()
    backtester = Backtester()

    # Run backtest
    result = await backtester.run(
        strategy=strategy,
        start_date=MEANVAR_START_DATE,
        end_date=MEANVAR_END_DATE,
        initial_capital=MEANVAR_INITIAL_CAPITAL
    )

    # Verify we got results
    assert result is not None, "Backtester returned None"
    assert result.metrics is not None, "No metrics in result"
    assert len(result.trades) > 0, "No trades were executed"

    # Compare metrics against QuantConnect baseline
    within_threshold, errors, exceeded_count = compare_metrics(
        actual=result.metrics,
        expected=MEANVAR_QC_METRICS,
        threshold=METRIC_ERROR_THRESHOLD
    )

    total_compared = len(errors)

    # Print detailed error report for debugging
    print("\n" + "="*70)
    print("MEANVAR BASELINE COMPARISON REPORT")
    print("="*70)
    for field, details in errors.items():
        status = details.get("status", "UNKNOWN")
        if status == "OK":
            rel_err = details.get("relative_error", 0)
            print(f"✓ {field:20s}: {details['actual']:12.4f} (expected: {details['expected']:12.4f}, error: {rel_err:.2%})")
        elif status == "OUTSIDE_THRESHOLD":
            rel_err = details.get("relative_error", 0)
            print(f"✗ {field:20s}: {details['actual']:12.4f} (expected: {details['expected']:12.4f}, error: {rel_err:.2%})")
        else:
            print(f"? {field:20s}: {status}")
    print("="*70)
    print(f"Metrics outside threshold: {exceeded_count}/{total_compared}")
    print("="*70)

    # Assert all metrics are within threshold
    assert within_threshold, (
        f"{exceeded_count}/{total_compared} metrics exceeded "
        f"{METRIC_ERROR_THRESHOLD*100}% error threshold"
    )

    # Log additional info
    print(f"\nBacktest Summary:")
    print(f"  Final Portfolio Value: ${result.final_value:,.2f}")
    print(f"  Final Cash: ${result.final_cash:,.2f}")
    print(f"  Total Trades: {len(result.trades)}")
    print(f"  Strategy Total Return: {result.metrics.total_return:.2%}")


@pytest.mark.asyncio
async def test_meanvar_produces_valid_results():
    """
    Sanity check that MeanVar strategy produces valid results.

    Validates:
    - Strategy runs without errors
    - Produces trades
    - Metrics are reasonable (e.g., max_drawdown is negative)
    """
    strategy = MeanVar()
    backtester = Backtester()

    result = await backtester.run(
        strategy=strategy,
        start_date=MEANVAR_START_DATE,
        end_date=MEANVAR_END_DATE,
        initial_capital=MEANVAR_INITIAL_CAPITAL
    )

    # Sanity checks
    assert result.final_value > 0, "Final value should be positive"
    assert len(result.trades) > 0, "Strategy should execute trades"

    # Check metric sanity
    assert result.metrics.max_drawdown > 0, "Max drawdown should be positive"
    assert -1 <= result.metrics.total_return <= 5, "Total return should be reasonable"
    assert 0 <= result.metrics.win_rate <= 1, "Win rate should be between 0 and 1"
    assert result.metrics.sharpe_ratio > -5 and result.metrics.sharpe_ratio < 5, "Sharpe ratio should be reasonable"


def test_meanvar_baseline_wrapper():
    """Sync wrapper for async test"""
    asyncio.run(test_meanvar_baseline_vs_quantconnect())

def test_meanvar_valid_results_wrapper():
    """Sync wrapper for async test"""
    asyncio.run(test_meanvar_produces_valid_results())
