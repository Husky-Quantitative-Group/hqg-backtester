from typing import Dict, Any, List
import pandas as pd

def run(algo) -> str:
    """
    Orchestrate:
      1) Load raw bars (MultiIndex ROW index: ['timestamp','symbol']; COLUMN index will be built).
      2) Pivot to a merged table with MultiIndex COLUMNS: (symbol, field) for OHLCV.
      3) Compute requested indicators (pure functions) and join as additional (symbol, INDICATOR) columns.
      4) Iterate timestamps:
         - Fill prior orders at current bar OPEN.
         - Build dict snapshot from the merged table for each symbol at ts.
         - Gate warmup: only call OnData if all required indicator columns for that symbol at ts are non-NaN.
         - Queue orders (filled next-bar-open).
         - Record equity.
      5) Write CSVs/plots/manifest; return output directory.
    """
    pass

def _pick_provider(cfg: Dict[str, Any]):
    """Return provider instance (e.g., CSV or IBKR) given config; no IO here."""
    pass

def _pivot_to_multiindex_columns(raw_bars: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw tall bars (MultiIndex ROWS: ['timestamp','symbol']) to a wide table with
    MultiIndex COLUMNS: (symbol, field), where field ∈ {'open','high','low','close','volume'}.
    Index remains the sorted timestamp index. Return the merged table.
    """
    pass

def _add_indicator_columns(
    merged: pd.DataFrame,
    indicator_requests: List[tuple[str, str, Dict[str, Any]]]
) -> pd.DataFrame:
    """
    Given the merged table with columns like (symbol,'close'), compute requested indicators
    per symbol using data.indicators functions and join them as new columns:
        (symbol, 'SMA20'), (symbol,'EMA50'), (symbol,'MACD'), etc.
    Return a new DataFrame with added columns.
    """
    pass

def _symbols_ready_at_ts(
    merged: pd.DataFrame,
    ts,
    required_cols_by_symbol: Dict[str, List[str]]
) -> List[str]:
    """
    Given a timestamp and a mapping of symbol -> list of required indicator names,
    return the subset of symbols whose required indicator columns are non-NaN at ts.
    Example: required_cols_by_symbol['AAPL'] = ['SMA20','MACD'] checks (('AAPL','SMA20'), ('AAPL','MACD')).
    """
    pass

def _bars_snapshot(merged: pd.DataFrame, symbols: List[str], ts) -> Dict[str, Any]:
    """
    Build the dict passed to OnData from the merged table at timestamp ts.
    For each symbol in 'symbols' that has a row at ts:
      snapshot[sym] = {
          "open": float, "high": float, "low": float, "close": float, "volume": float,
          ...any indicator columns present for that symbol at ts...
      }
    """
    pass

# Suggested helpers:
# - _output_dir(cfg) -> str
# - _timeline(merged) -> iterable of timestamps (merged.index)
# - _open_price(merged, ts, symbol) -> float  (used by broker)
