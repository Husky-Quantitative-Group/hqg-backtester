from typing import Dict, Any, List, Tuple
import pandas as pd

def sma(series: pd.Series, period: int) -> pd.Series:
    """Return SMA(series, period); aligned to series index; NaN until sufficient history."""
    pass

def ema(series: pd.Series, period: int) -> pd.Series:
    """Return EMA(series, period); aligned to series index; standard EMA convention."""
    pass

def macd(series: pd.Series, fast: int, slow: int, signal: int) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Return (macd_line, signal_line, histogram); all aligned to index; NaNs during warmup."""
    pass

def add_requested_indicators(
    merged: pd.DataFrame,
    indicator_requests: List[tuple[str, str, Dict[str, Any]]]
) -> pd.DataFrame:
    """
    For each (symbol, name, params) in indicator_requests:
      - Use merged[(symbol,'close')] as the input series.
      - Compute the indicator via the pure functions above.
      - Add a single primary output column for V1:
          SMA → (symbol, f"SMA{period}")
          EMA → (symbol, f"EMA{period}")
          MACD → (symbol, "MACD")  # choose histogram for V1 (or parameterize)
      - Leave NaNs during warmup; engine checks readiness at runtime.

    Return a new DataFrame with added MultiIndex columns; do not modify input in place.
    """
    pass

def required_cols_by_symbol(
    indicator_requests: List[tuple[str, str, Dict[str, Any]]]
) -> Dict[str, List[str]]:
    """
    Derive a mapping {symbol: [indicator_column_names]} that must be non-NaN at ts
    to call OnData. Names must match the columns created in add_requested_indicators().
    Example: ('AAPL','SMA', {'period':20}) → require 'SMA20' for AAPL.
    """
    pass
