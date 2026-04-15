import numpy as np
from typing import Dict, List
from datetime import datetime
from hqg_algorithms import Slice


class PortfolioRecorder:
    """Equity, OHLC, and per-symbol weights in a single `snapshot()` call. """
    
    def __init__(self, n_bars: int, symbols: List[str]):
        """
        Args:
            n_bars: Number of timestamps (len(timestamps)) to pre-allocate arrays.
            symbols: Ordered list of ticker symbols in the universe.
        """
        self._n_bars = n_bars
        self._symbols = list(symbols)
        self._n_symbols = len(symbols)
        self._symbol_idx: Dict[str, int] = {s: i for i, s in enumerate(symbols)}
        self._idx = 0  # write cursor

        # pre-allocate arrays
        self._timestamps = np.empty(n_bars, dtype=object)
        self._ohlc = np.empty((n_bars, 4), dtype=np.float64)    # open, high, low, close
        self._equity = np.empty(n_bars, dtype=np.float64)   # total value (equity curve)
        self._weights = np.zeros((n_bars, self._n_symbols), dtype=np.float64)  # per-symbol weights (n_bars, n_symbols)

    def snapshot(
        self,
        timestamp: datetime,
        cash: float,
        positions: Dict[str, float],
        slice_obj: Slice,
        prices: Dict[str, float],
        total_value: float,
    ) -> None:
        """ Record one bar of portfolio state. Called once per bar, before rebalance. """
        
        i = self._idx

        self._timestamps[i] = timestamp
        self._equity[i] = total_value

        # ohlc
        p_open = cash
        p_high = cash
        p_low = cash
        p_close = cash

        for symbol, shares in positions.items():
            if shares <= 0:
                continue
            bar = slice_obj.bar(symbol)
            if bar is None:
                continue
            p_open += shares * bar.open
            p_high += shares * bar.high
            p_low += shares * bar.low
            p_close += shares * bar.close

        self._ohlc[i, 0] = p_open
        self._ohlc[i, 1] = p_high
        self._ohlc[i, 2] = p_low
        self._ohlc[i, 3] = p_close

        # per-symbol weights (decimal)
        if total_value > 0:
            for symbol, shares in positions.items():
                if shares <= 0:
                    continue
                if symbol not in prices or symbol not in self._symbol_idx:
                    continue
                j = self._symbol_idx[symbol]
                self._weights[i, j] = (prices[symbol] * shares) / total_value

        self._idx += 1


    def to_ohlc(self) -> Dict[datetime, Dict[str, float]]:
        """
        Returns portfolio OHLC as:
        { datetime: {"open": ..., "high": ..., "low": ..., "close": ...} }
        """
        n = self._idx
        result = {}
        for i in range(n):
            result[self._timestamps[i]] = {
                "open": float(self._ohlc[i, 0]),
                "high": float(self._ohlc[i, 1]),
                "low": float(self._ohlc[i, 2]),
                "close": float(self._ohlc[i, 3]),
            }
        return result

    def to_equity_curve(self) -> Dict[datetime, float]:
        """
        Returns equity curve as {timestamp: total_value}.
        """
        n = self._idx
        return {
            self._timestamps[i]: float(self._equity[i])
            for i in range(n)
        }

    def to_holding_weights(self) -> Dict[datetime, List[Dict]]:
        """
        Returns holding weights as:
        {
            str(timestamp): { symbol: weight, ... },
            ...
        }
        """
        n = self._idx
        result = {}
        for i in range(n):
            weights_at_t = {}
            for j, symbol in enumerate(self._symbols):
                w = self._weights[i, j]
                weights_at_t[symbol] = float(w)     # include weights of 0 if not held
            result[self._timestamps[i]] = weights_at_t
        return result