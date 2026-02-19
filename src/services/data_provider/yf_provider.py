import hashlib
import os
import threading
from pathlib import Path

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List
import logging
from .base_provider import BaseDataProvider
from src.config.settings import settings

logger = logging.getLogger(__name__)

# One lock per cache key; protects both the file write and the double-check read
# under lock. Module-level so all YFDataProvider instances share state.
_cache_locks: dict[str, threading.Lock] = {}
_cache_locks_mutex = threading.Lock()


def _get_cache_lock(key: str) -> threading.Lock:
    """Return the per-key lock, creating it if necessary."""
    with _cache_locks_mutex:
        if key not in _cache_locks:
            _cache_locks[key] = threading.Lock()
        return _cache_locks[key]


class YFDataProvider(BaseDataProvider):
    """
    Fetches historical market data using yfinance with a parquet-backed cache.

    Cache key: sha256("{symbol}|{start.date()}|{end.date()}|{interval}")[:16]
    Each symbol is cached independently so overlapping requests share files.
    """

    def _cache_key(self, symbol: str, start_date: datetime, end_date: datetime, interval: str) -> str:
        raw = f"{symbol}|{start_date.date()}|{end_date.date()}|{interval}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        return Path(settings.DATA_CACHE_DIR) / f"{key}.parquet"

    def _read_cache(self, key: str) -> pd.DataFrame | None:
        path = self._cache_path(key)
        if path.exists():
            return pd.read_parquet(path)
        return None

    def _write_cache(self, key: str, df: pd.DataFrame) -> None:
        """Write to .tmp then os.replace() atomically."""
        path = self._cache_path(key)
        tmp_path = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp_path)
        os.replace(tmp_path, path)

    def _extract_symbol(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Extract a flat per-symbol OHLCV DataFrame from a yf.download() result.
        """
        fields = ["Open", "High", "Low", "Close", "Volume"]
        if isinstance(data.columns, pd.MultiIndex):
            if symbol not in data.columns.get_level_values(0):
                raise ValueError(f"Symbol {symbol} not found in download result")
            sub = data[symbol]
            sym_data = {f.lower(): sub[f] for f in fields if f in sub.columns}
        else:
            sym_data = {f.lower(): data[f] for f in fields if f in data.columns}
        return pd.DataFrame(sym_data, index=data.index)


    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: timedelta = timedelta(days=1),
    ) -> pd.DataFrame:
        """
        Return a MultiIndex (symbol, field) DataFrame for the requested symbols
        and date range, reading from the parquet cache where possible and
        fetching from Yahoo Finance only for cache misses.
        """
        symbols = [s.upper() for s in symbols]
        interval = self._get_yfinance_interval(bar_size)

        keys = {s: self._cache_key(s, start_date, end_date, interval) for s in symbols}
        misses = [s for s in symbols if self._read_cache(keys[s]) is None]

        if misses:
            # acquire per-key locks in sorted key order to prevent deadlock
            sorted_miss_keys = sorted({keys[s] for s in misses})
            locks = [_get_cache_lock(k) for k in sorted_miss_keys]
            for lock in locks:
                lock.acquire()

            try:
                still_missing = [s for s in misses if self._read_cache(keys[s]) is None]

                if still_missing:
                    # one network call for all remaining misses
                    logger.info(f"Fetching data for {still_missing} from {start_date} to {end_date}")
                    raw = yf.download(
                        tickers=still_missing,
                        start=start_date,
                        end=end_date + timedelta(days=1),
                        interval=interval,
                        progress=False,
                        group_by="ticker",
                        auto_adjust=True,
                    )

                    if raw.empty:
                        raise ValueError(f"No data found for symbols {still_missing}")

                    # write each symbol atomically
                    for symbol in still_missing:
                        sym_df = self._extract_symbol(raw, symbol)
                        self._write_cache(keys[symbol], sym_df)

            finally:
                for lock in reversed(locks):
                    lock.release()

        # assemble MultiIndex DataFrame from cache
        frames = {}
        for symbol in symbols:
            sym_df = self._read_cache(keys[symbol])
            if sym_df is None:
                raise ValueError(f"Cache miss after fetch for symbol {symbol}")
            for field in ["open", "high", "low", "close", "volume"]:
                if field in sym_df.columns:
                    frames[(symbol, field)] = sym_df[field]

        if not frames:
            raise ValueError(f"No data available for {symbols}")

        result = pd.DataFrame(frames)
        result.columns = pd.MultiIndex.from_tuples(result.columns)

        logger.info(f"Returning {len(result)} bars for {symbols}")
        return result

    def _get_yfinance_interval(self, bar_size: timedelta) -> str:
        """Convert timedelta to yfinance interval string."""
        total_minutes = int(bar_size.total_seconds() / 60)

        if total_minutes == 1:
            return "1m"
        elif total_minutes == 5:
            return "5m"
        elif total_minutes == 15:
            return "15m"
        elif total_minutes == 30:
            return "30m"
        elif total_minutes == 60:
            return "1h"
        elif total_minutes == 1440:
            return "1d"
        elif total_minutes == 10080:
            return "1wk"
        elif total_minutes >= 43200:
            return "1mo"
        else:
            raise ValueError(f"Unsupported bar size: {bar_size}")
