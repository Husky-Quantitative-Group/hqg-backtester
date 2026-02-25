import sys
import time
import cProfile
import pstats
import io
import os
import pandas as pd
from hqg_algorithms import Strategy, BarSize
from typing import Dict, Any
from src.models.execution import ExecutionPayload, RawExecutionResult
from src.models.portfolio import Portfolio
from src.models.request import BacktestRequestError
from src.services.backtester import Backtester

PROFILE = os.environ.get("HQG_PROFILE", "0") == "1"


def main():
    try:
        json_payload = sys.stdin.read()
        payload = ExecutionPayload.model_validate_json(json_payload)

        if PROFILE:
            profiler = cProfile.Profile()
            profiler.enable()

        start = time.time()
        result_dict = execute_backtest(payload)
        result_dict["execution_time"] = time.time() - start

        if PROFILE:
            profiler.disable()
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.sort_stats("cumulative")
            stats.print_stats(40)
            sys.stderr.write(f"\n{'='*70}\n")
            sys.stderr.write("CONTAINER PROFILE\n")
            sys.stderr.write(f"{'='*70}\n")
            sys.stderr.write(stream.getvalue())

        result = RawExecutionResult(**result_dict)
        sys.stdout.write(result.model_dump_json())
        sys.exit(0)

    except Exception as e:
        errors = BacktestRequestError()
        errors.add(str(e))
        error_result = RawExecutionResult(
            trades=[],
            equity_curve={},
            ohlc={},
            final_value=0.0,
            final_cash=0.0,
            final_positions={},
            execution_time=0.0,
            errors=errors,
            bar_size=payload.bar_size
        )
        sys.stdout.write(error_result.model_dump_json())
        sys.exit(1)


def execute_backtest(payload: ExecutionPayload) -> Dict[str, Any]:
    """
    Execute the backtest by running the strategy code with market data.

    Market data format (JSON):
    {
      "AAPL": {
        "date": ["2023-01-01", "2023-01-02"],
        "open": [149, 151],
        "high": [151, 153],
        "low": [148, 150],
        "close": [150, 152],
        "volume": [1000, 1100]
      },
      "TSLA": { ... }
    }
    """
    errors = BacktestRequestError()
    backtester = Backtester()

    try:
        # Convert market_data JSON to pandas DataFrame (MultiIndex format)
        data = json_to_dataframe(payload.market_data)

        # TODO: refactor w/ StrategyLoader (no write)
        # Load strategy class
        strategy_namespace = {}
        exec(payload.strategy_code, strategy_namespace)

        # Find Strategy subclass
        strategy_class = None
        for _, obj in strategy_namespace.items():
            if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
                strategy_class = obj
                break

        if strategy_class is None:
            raise ValueError("No Strategy subclass found in strategy_code")
        strategy = strategy_class()

        # Initialize portfolio
        symbols = strategy.universe()
        portfolio = Portfolio(initial_cash=payload.initial_capital, symbols=symbols)

        # Run backtest loop
        cadence = strategy.cadence()
        trades, ohlc = backtester._run_loop(strategy, data, portfolio, cadence)

        # Get final prices
        final_prices = backtester._get_final_prices(data, symbols)

        return {
            "trades": [t.model_dump() for t in trades],
            "equity_curve": {ts.isoformat(): value for ts, value in portfolio.equity_curve.items()},
            "ohlc": ohlc,
            "final_value": portfolio.get_total_value(final_prices),
            "final_cash": portfolio.cash,
            "final_positions": portfolio.positions.copy(),
            "errors": errors,
            "bar_size": cadence.bar_size
        }

    except Exception as e:
        errors.add(f"Strategy execution error: {str(e)}")
        return {
            "trades": [],
            "equity_curve": {},
            "ohlc": {},
            "final_value": 0.0,
            "final_cash": 0.0,
            "final_positions": {},
            "errors": errors,
            "bar_size": BarSize.DAILY   # in case of failure before cadence defined
        }


def json_to_dataframe(market_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert JSON market data to pandas DataFrame with MultiIndex columns.

    Input: {"AAPL": {"date": [...], "open": [...], ...}}
    Output: DataFrame with DatetimeIndex and MultiIndex columns (symbol, field)
    """
    frames = {}
    for symbol, data_dict in market_data.items():
        df = pd.DataFrame(data_dict)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        frames[symbol] = df

    # Build MultiIndex DataFrame
    all_data = []
    for symbol, df in frames.items():
        for field in ["open", "high", "low", "close", "volume"]:
            if field in df.columns:
                all_data.append((symbol, field, df[field]))

    if not all_data:
        return pd.DataFrame()

    # Create MultiIndex columns
    tuples = [(symbol, field) for symbol, field, _ in all_data]
    columns = pd.MultiIndex.from_tuples(tuples)

    # Create DataFrame with MultiIndex columns
    formatted = pd.DataFrame({i: data for i, (_, _, data) in enumerate(all_data)})
    formatted.columns = columns

    return formatted


if __name__ == "__main__":
    main()
