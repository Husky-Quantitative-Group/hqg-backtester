import sys
import time
import cProfile
import pstats
import io
import os
import pandas as pd
from hqg_algorithms import Strategy, BarSize, Slice, Bar
from types import MappingProxyType
from typing import Dict, Any, Mapping
from src.models.execution import ExecutionPayload, RawExecutionResult
from src.models.portfolio import Portfolio
from src.models.recorder import PortfolioRecorder
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
            holding_weights={},
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
        alt_frames = json_to_alt_frames(payload.alt_data)
        alt_state = AltDataState(alt_frames)

        # Pre-build timestamp:Slice dict (avoid per-step MultiIndex slicing in loop)
        slices, timestamps = precompute_slices(data, alt_state)

        # TODO: refactor w/ StrategyLoader (no write)
        # Load strategy class
        strategy_namespace = {}

        # Inject config module if config_params provided
        if payload.config_params:
            import types
            config_module = types.ModuleType('config')
            for key, value in payload.config_params.items():
                setattr(config_module, key, value)
            sys.modules['config'] = config_module

        exec(payload.strategy_code, strategy_namespace)

        # Find Strategy subclass
        strategy_class = None
        for _, obj in strategy_namespace.items():
            if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
                strategy_class = obj
                break

        if strategy_class is None:
            raise ValueError("No Strategy subclass found in strategy_code")
        strategy_logs: list[str] = []
        strategy_class._log_handler = strategy_logs.append
        strategy = strategy_class()

        symbols = strategy.universe
        portfolio = Portfolio(initial_cash=payload.initial_capital, symbols=symbols)
        recorder = PortfolioRecorder(n_bars=len(timestamps), symbols=symbols)

        # run backtest loop; recorder accumulates ohlc, equity, weights
        trades = backtester._run_loop(strategy, slices, timestamps, portfolio, recorder)

        # extract all time-series from recorder
        equity_curve = recorder.to_equity_curve()
        ohlc = recorder.to_ohlc()
        holding_weights = recorder.to_holding_weights()

        # Get final prices
        final_slice = slices[timestamps[-1]]
        final_prices = backtester._get_close(final_slice, symbols)

        return {
            "orders": [t.model_dump() for t in trades],
            "equity_curve": {ts.isoformat(): v for ts, v in equity_curve.items()},
            "ohlc": {ts.isoformat(): v for ts, v in ohlc.items()},
            "holding_weights": {ts.isoformat(): v for ts, v in holding_weights.items()},
            "final_value": portfolio.get_total_value(final_prices),
            "final_cash": portfolio.cash,
            "final_positions": portfolio.positions.copy(),
            "errors": errors,
            "bar_size": strategy.cadence.bar_size,
            "strategy_logs": strategy_logs,
        }

    except Exception as e:
        errors.add(f"Strategy execution error: {str(e)}")
        return {
            "orders": [],
            "equity_curve": {},
            "ohlc": {},
            "holding_weights": {},
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


def json_to_alt_frames(alt_data: Dict[str, Any] | None) -> Dict[str, pd.DataFrame]:
    """
    Reconstruct per-series raw alternative data frames from the JSON payload.

    No cross-series alignment is attempted, since revisions of different
    series have no row-to-row correspondence.

    Input: {"FRED.GDP": {"date": [...], "value": [...], "available_at": [...]}}
    Output: {"FRED.GDP": DataFrame indexed by observation date}
    """
    frames = {}
    if alt_data is None:
        return frames

    for series_id, data_dict in alt_data.items():
        if not data_dict:
            frames[series_id] = pd.DataFrame(columns=["value", "available_at"]).rename_axis("date")
            continue

        if "date" not in data_dict:
            raise ValueError(f"Alt data payload for '{series_id}' is missing 'date'")

        df = pd.DataFrame(data_dict)
        df["date"] = pd.to_datetime(df["date"])
        for column in df.columns:
            if column != "date" and (str(column).endswith("_at") or str(column).endswith("_date")):
                df[column] = pd.to_datetime(df[column])
        frames[series_id] = df.set_index("date")

    return frames


_EMPTY_ALT_VIEW = MappingProxyType({})


class AltDataState:
    """
    Point-in-time state machine for revision-tracked alternative data.

    This is the only place that compares available_at against the simulated
    clock. Slice receives already-filtered immutable snapshots.
    """

    def __init__(self, frames: Dict[str, pd.DataFrame]):
        self._state: dict[str, dict[pd.Timestamp, float]] = {}
        self._dirty: dict[str, bool] = {}
        self._frozen: dict[str, Mapping[pd.Timestamp, float]] = {}
        self._events: list[tuple[pd.Timestamp, str, pd.Timestamp, float]] = []
        self._cursor = 0
        self._clock: pd.Timestamp | None = None
        self.changed_this_call = False

        for series_id, frame in frames.items():
            self._state[series_id] = {}
            self._dirty[series_id] = False
            self._frozen[series_id] = _EMPTY_ALT_VIEW

            if frame.empty:
                continue
            if "available_at" not in frame.columns or "value" not in frame.columns:
                raise ValueError(f"Alt data frame for '{series_id}' must include value and available_at")

            for observation_date, row in frame.iterrows():
                available_at = pd.Timestamp(row["available_at"])
                if pd.isna(available_at):
                    raise ValueError(
                        f"Alt data frame for '{series_id}' has missing available_at "
                        f"at observation {observation_date}"
                    )
                if pd.isna(row["value"]):
                    raise ValueError(
                        f"Alt data frame for '{series_id}' has missing value "
                        f"at observation {observation_date}"
                    )
                self._events.append(
                    (
                        available_at,
                        series_id,
                        pd.Timestamp(observation_date),
                        float(row["value"]),
                    )
                )

        self._events.sort(key=lambda event: (event[0], event[1], event[2]))
        self._series_ids = tuple(self._state)

    def series_ids(self) -> tuple[str, ...]:
        return self._series_ids

    def advance_to(self, t: pd.Timestamp) -> None:
        self.changed_this_call = False
        clock = pd.Timestamp(t)
        if self._clock is not None and clock < self._clock:
            raise ValueError("AltDataState can only advance forward in time")
        self._clock = clock

        while self._cursor < len(self._events) and self._events[self._cursor][0] < clock:
            available_at, series_id, observation_date, value = self._events[self._cursor]
            if available_at > clock:
                raise AssertionError(
                    f"Leakage prevented: {series_id} observation {observation_date} "
                    f"has available_at={available_at} > clock={clock}"
                )
            self._state[series_id][observation_date] = value
            self._dirty[series_id] = True
            self.changed_this_call = True
            self._cursor += 1

    def latest(self, series_id: str) -> float | None:
        state = self._state.get(series_id)
        if not state:
            return None
        return state[max(state)]

    def snapshot(self, series_id: str) -> dict[pd.Timestamp, float]:
        return dict(self._state.get(series_id, {}))

    def snapshot_view(self, series_id: str) -> Mapping[pd.Timestamp, float]:
        if series_id not in self._state:
            return _EMPTY_ALT_VIEW
        if self._dirty[series_id]:
            self._frozen[series_id] = MappingProxyType(dict(self._state[series_id]))
            self._dirty[series_id] = False
        return self._frozen[series_id]


def precompute_slices(data: pd.DataFrame, alt_state: AltDataState | None = None) -> tuple[Dict, list]:
    """
    Build a dictionary of timestamps: slices for backtest loop
    """
    if not data.index.is_monotonic_increasing:
        raise ValueError("Market data timestamps must be sorted")

    if data.index.has_duplicates:
        raise ValueError("Market data contains duplicate timestamps")

    timestamps = data.index.tolist()
    columns = data.columns.tolist()  # [(symbol, field), ...]; e.g. [('AAPL', 'close'), ...]
    values = data.values  # shape: (n_timestamps, n_columns)

    symbols = list(dict.fromkeys(s for s, _ in columns))

    # Build column index lookup: {(symbol, field): col_index}
    col_index = {(s, f): j for j, (s, f) in enumerate(columns)}

    slices = {}
    alt_history = None
    for i, ts in enumerate(timestamps):
        bars = {}
        for s in symbols:
            bars[s] = Bar(
                open=float(values[i, col_index[(s, "open")]]),
                high=float(values[i, col_index[(s, "high")]]),
                low=float(values[i, col_index[(s, "low")]]),
                close=float(values[i, col_index[(s, "close")]]),
                volume=float(values[i, col_index[(s, "volume")]]) if (s, "volume") in col_index else None,
            )
        if alt_state is not None:
            alt_state.advance_to(ts)
            if alt_history is None or alt_state.changed_this_call:
                alt_history = {
                    series_id: alt_state.snapshot_view(series_id)
                    for series_id in alt_state.series_ids()
                }
        slices[ts] = Slice(bars, alt_history=alt_history)

    return slices, timestamps


if __name__ == "__main__":
    main()
