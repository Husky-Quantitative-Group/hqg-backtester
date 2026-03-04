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
    BarSize.MONTHLY: "M",
    BarSize.QUARTERLY: "Q",
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
      calculated after the fact.
    - If the cache already covers part of the requested range, merge new data in.
    - Expectation is that cache is wiped daily by external process.
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
                logger.warning(f"Corrupt cache for {symbol}, deleting")
                with _get_cache_lock(symbol):
                    path.unlink(missing_ok=True)

        return None

    def _write_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """Atomic write via tmp + os.replace()."""
        path = self._cache_path(symbol)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp)
        os.replace(tmp, path)



    # NOTE: edge case for holidays. Say our cached data starts on 1/2/2024 (since 1/1/2024 was a holiday
    # with no data). If a user requests a range starting on 1/1/2024, the requested start date
    # won't match our cached start date, which would incorrectly trigger a data re-fetch.

    # NOTE: Tickers with limited history (e.g., IPO'd in 2015) will have cache_min far
    # after _DEFAULT_HISTORY_START. Without this check, cache_min > fetch_start would
    # cause _cache_covers to return False on every call, triggering endless re-fetches.
    def _cache_covers(self, symbol: str, fetch_start: datetime, fetch_end: datetime) -> bool:
        """
        Check if cache is full enough to skip a fetch.
        End date: cache must extend to fetch_end.
        Start date: cache must start within 30 days of fetch_start (generous buffer because cache_min alr <= year 2000)
        """
        cached = self._read_cache(symbol)
        if cached is None:
            return False
        
        cache_min = cached.index.min().date()
        cache_max = cached.index.max().date()

        # If we're asking for our default range (or narrower), a previous fetch already requested back to 2000.
        if fetch_start >= _DEFAULT_HISTORY_START:
            start_covered = True
        else:
            # Requesting earlier than our default floor: check if cache actually has it
            start_covered = cache_min <= (fetch_start + timedelta(days=30)).date()

        end_covered = cache_max >= fetch_end.date()
        
        covers = end_covered and start_covered
        logger.debug(
            f"_cache_covers({symbol}): cache_range={cache_min}..{cache_max}, "
            f"requested={fetch_start.date()}..{fetch_end.date()}, covers={covers}"
        )
        return covers

    def _fetch_from_yf(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, pd.DataFrame]:
        """
        Download daily data for symbols between start and end (inclusive)
        and return a dict mapping each symbol to its flat OHLCV DF.
        """
        logger.info(f"yfinance download: {symbols}  {start.date()} -> {end.date()}")

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
        """
        Resample daily bars to a coarser frequency. 

        Uses manual grouping instead of pd.resample() so that the output 
        index contains the last actual trading date in each period.
        """
        rule = _RESAMPLE_RULES.get(bar_size)
        if rule is None:
            return df

        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        agg = {k: v for k, v in agg.items() if k in df.columns}

        # assign each daily row to a calendar period bucket & aggregate
        periods = df.index.to_period(rule)
        grouped = df.groupby(periods)
        resampled = grouped.agg(agg).dropna(how="all")

        # replace period-end dates with the last real trading date per group
        last_date_map = {period: group.index[-1] for period, group in grouped}
        real_dates = [last_date_map[p] for p in resampled.index]
        resampled.index = pd.DatetimeIndex(real_dates, name=df.index.name)

        return resampled

    def _last_trading_day(self) -> datetime:
        """Approximate last trading day (no holiday calendar)."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if today.weekday() == 5:      # Saturday
            return today - timedelta(days=1)
        elif today.weekday() == 6:    # Sunday
            return today - timedelta(days=2)
        return today

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

        # widen the fetch window so the cache is useful for future requests
        fetch_start = min(start_date, _DEFAULT_HISTORY_START)
        fetch_end = self._last_trading_day()

        # lockless pre-scan
        probable_misses = [s for s in symbols if not self._cache_covers(s, fetch_start, fetch_end)]

        # lock + double-check + fetch
        if probable_misses:
            sorted_misses = sorted(set(probable_misses))
            locks = {s: _get_cache_lock(s) for s in sorted_misses}

            for s in sorted_misses:
                locks[s].acquire()
            try:
                confirmed_misses = [s for s in sorted_misses if not self._cache_covers(s, fetch_start, fetch_end)]

                if confirmed_misses:
                    new_data = self._fetch_from_yf(confirmed_misses, fetch_start, fetch_end)

                    for symbol in confirmed_misses:
                        if symbol not in new_data:
                            raise ValueError(f"No data returned for {symbol}")

                        existing = self._read_cache(symbol)
                        if existing is not None:
                            merged = pd.concat([existing, new_data[symbol]])
                            merged = merged[~merged.index.duplicated(keep="last")]
                            merged = merged.sort_index()
                        else:
                            merged = new_data[symbol]
                        self._write_cache(symbol, merged)
            finally:
                for s in reversed(sorted_misses):
                    locks[s].release()

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