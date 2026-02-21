import os
import threading
from pathlib import Path
from hqg_algorithms import BarSize
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

# Earliest date we'll ever request from yfinance. Keeps cache broad so
# future requests for the same symbol are almost always a hit.
_DEFAULT_HISTORY_START = datetime(2000, 1, 1)

_RESAMPLE_RULES = {
    BarSize.DAILY: None,
    BarSize.WEEKLY: "W-FRI",
    BarSize.MONTHLY: "ME",
    BarSize.QUARTERLY: "QE",
}


def _get_cache_lock(symbol: str) -> threading.Lock:
    """Return the per-symbol lock, creating it if necessary."""
    with _cache_locks_mutex:
        if symbol not in _cache_locks:
            _cache_locks[symbol] = threading.Lock()
        return _cache_locks[symbol]


class YFDataProvider(BaseDataProvider):
    """
    Fetches historical daily market data via yfinance with a symbol-level
    parquet cache.

    Design notes:
    - {SYMBOL}.parquet containing all daily OHLCV rows we have for that symbol.
    - Always fetch daily bars. Coarser intervals (weekly, monthly) are
      calulated after the fact.
    - If the cache already covers part of the requested range, refetch + update cache.
    - Cache is wiped daily by external process; optimize for *intra-day* reuse across users / runs.
    """
    def __init__(self):
        Path(settings.DATA_CACHE_DIR).mkdir(parents=True, exist_ok=True)

    def _cache_path(self, symbol: str) -> Path:
        return Path(settings.DATA_CACHE_DIR) / f"{symbol}.parquet"

    def _read_cache(self, symbol: str) -> pd.DataFrame | None:
        path = self._cache_path(symbol)
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
            except Exception:
                logger.warning(f"Corrupt cache for {symbol}, will re-fetch")
        return None

    def _write_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """Atomic write via tmp + os.replace()."""
        path = self._cache_path(symbol)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp)
        os.replace(tmp, path)

    def _fetch_from_yf(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, pd.DataFrame]:
        """
        Download daily data for symbols between start and end (inclusive)
        and return a dict mapping each symbol to its flat OHLCV DF
        """
        logger.info(f"yfinance download: {symbols}  {start.date()} → {end.date()}")

        raw = yf.download(
            tickers=symbols,
            start=start,
            end=end + timedelta(days=1),
            interval="1d",
            progress=False,
            group_by="ticker",
            auto_adjust=True,
        )

        if raw.empty:
            raise ValueError(f"yfinance returned no data for {symbols}")

        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            result[symbol] = self._extract_symbol(raw, symbol)
        return result

    def _extract_symbol(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Extract a flat per-symbol OHLCV DataFrame from a yf.download() result.
        """        
        fields = ["Open", "High", "Low", "Close", "Volume"]

        if isinstance(data.columns, pd.MultiIndex):
            level_values = data.columns.get_level_values(0)
            if symbol in level_values:
                sub = data[symbol]
            elif symbol.upper() in level_values:
                sub = data[symbol.upper()]
            else:
                raise ValueError(f"Symbol {symbol} not in download result")
            cols = {f.lower(): sub[f] for f in fields if f in sub.columns}
        else:
            # single-symbol download - no MultiIndex
            cols = {f.lower(): data[f] for f in fields if f in data.columns}

        df = pd.DataFrame(cols, index=data.index)
        df.index.name = "date"
        return df.dropna(how="all")

    def _resample(self, df: pd.DataFrame, bar_size: BarSize) -> pd.DataFrame:
        rule = _RESAMPLE_RULES.get(bar_size)
        if rule is None:   # Daily
            return df

        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        agg = {k: v for k, v in agg.items() if k in df.columns}
        return df.resample(rule).agg(agg).dropna(how="all")

    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: BarSize = BarSize.DAILY
    ) -> pd.DataFrame:
        """
        Return a MultiIndex (symbol, field) DataFrame for the requested
        symbols and date range.

        Data is always cached/fetched as daily bars and resampled to
        bar_size on the fly.
        """
        # TODO: change data provider to make hourly backtests meaningful.
        # Until then, don't support it (enforced in hqg-algorithms)
        # NOTE: fail faster?
        if bar_size < timedelta(days=1):
            raise ValueError(
                "Intraday bar sizes are not supported; minimum is 1 day."
            )

        symbols = [s.upper() for s in symbols]

        # widen the fetch window so the cache is useful for future requests
        fetch_start = min(start_date, _DEFAULT_HISTORY_START)
        fetch_end = datetime.now()

        # per-symbol: check cache, update if needed
        for symbol in symbols:
            lock = _get_cache_lock(symbol)
            with lock:
                cached = self._read_cache(symbol)

                if cached is not None and fetch_start >= cached.index.min() and fetch_end <= cached.index.max():
                    continue    # cache is sufficient

                # refetch + write
                new_data = self._fetch_from_yf([symbol], fetch_start, fetch_end)
                if symbol not in new_data:
                    raise ValueError(f"No data returned for {symbol}")
                self._write_cache(symbol, new_data[symbol])


        # build df from cache
        frames: dict[tuple[str, str], pd.Series] = {}

        for symbol in symbols:
            sym_df = self._read_cache(symbol)
            if sym_df is None:
                raise ValueError(f"Cache miss after fetch for {symbol}")

            # slice to requested window
            sym_df = sym_df.loc[
                (sym_df.index >= pd.Timestamp(start_date))
                & (sym_df.index <= pd.Timestamp(end_date))
            ]

            # resample if needed
            sym_df = self._resample(sym_df, bar_size)

            for field in ("open", "high", "low", "close", "volume"):
                if field in sym_df.columns:
                    frames[(symbol, field)] = sym_df[field]

        if not frames:
            raise ValueError(f"No data available for {symbols}")

        result = pd.DataFrame(frames)
        result.columns = pd.MultiIndex.from_tuples(result.columns)

        logger.info(
            f"Returning {len(result)} bars for {symbols} "
            f"({start_date.date()} to {end_date.date()}, bar_size={bar_size})"
        )
        return result