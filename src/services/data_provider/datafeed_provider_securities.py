import os
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pandas as pd
from datafeed import Config, DataFeed
from hqg_algorithms import BarSize

from .base_provider import BaseDataProvider


logger = logging.getLogger(__name__)

# One lock per cache key; protects both the file write and the double-check
# read under lock. Module-level so all provider instances share state.
_cache_locks: dict[str, threading.Lock] = {}
_cache_locks_mutex = threading.Lock()

# Earliest date we'll request from the datafeed. This keeps cache broad so
# future requests for the same symbol are usually a cache hit.
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


class DataFeedSecuritiesProvider(BaseDataProvider):
    """
    Adapter from hqg-datafeed's MarketData API to the backtester provider
    contract.

    This keeps the previous provider's symbol-level parquet cache behavior.
    hqg-datafeed fills cache misses with daily securities data, and coarser
    bars are calculated from cached daily bars after the fact.
    """

    def __init__(self, feed: DataFeed | None = None, cache_dir: str | Path | None = None):
        self.feed = feed or DataFeed(Config())
        if cache_dir is None:
            from src.config.settings import settings

            cache_dir = settings.DATA_CACHE_DIR
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, symbol: str) -> Path:
        return self.cache_dir / f"{symbol}.parquet"

    def _read_cache(self, symbol: str) -> pd.DataFrame | None:
        path = self._cache_path(symbol)
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
            except Exception:
                logger.warning("Corrupt cache for %s, deleting", symbol)
                with _get_cache_lock(symbol):
                    path.unlink(missing_ok=True)
        return None

    def _write_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """Atomically write a symbol cache file via tmp + os.replace()."""
        path = self._cache_path(symbol)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp)
        os.replace(tmp, path)

    def _cache_covers(self, symbol: str, fetch_start: datetime, fetch_end: datetime) -> bool:
        """
        Check whether cache is broad enough to skip a fetch.

        End date: cache must extend to fetch_end.
        Start date: for default-or-newer requests, a previous cache fill already
        requested back to _DEFAULT_HISTORY_START. For earlier requests, allow a
        small buffer for non-trading starts such as holidays.
        """
        cached = self._read_cache(symbol)
        if cached is None:
            return False

        cache_min = cached.index.min().date()
        cache_max = cached.index.max().date()

        # Tickers with limited history, such as recent IPOs, can have cache_min
        # far after _DEFAULT_HISTORY_START. Treat the default fetch floor as
        # covered so those symbols do not re-fetch endlessly.
        if fetch_start >= _DEFAULT_HISTORY_START:
            start_covered = True
        else:
            # If a request starts on a holiday/weekend, the first cached trading
            # day can be after fetch_start even though the cache is complete.
            start_covered = cache_min <= (fetch_start + timedelta(days=30)).date()

        end_covered = cache_max >= fetch_end.date()
        covers = end_covered and start_covered
        logger.debug(
            "_cache_covers(%s): cache_range=%s..%s, requested=%s..%s, covers=%s",
            symbol,
            cache_min,
            cache_max,
            fetch_start.date(),
            fetch_end.date(),
            covers,
        )
        return covers

    def _fetch_from_datafeed(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch daily securities data and return flat OHLCV frames by symbol.
        """
        logger.info("datafeed securities fetch: %s %s -> %s", symbols, start.date(), end.date())
        market_data = self.feed.get_data(
            securities=symbols,
            alt_data=[],
            start=start,
            end=end,
        )
        data = market_data.securities
        if data.empty:
            raise ValueError(f"No data available for {symbols}")

        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            result[symbol] = self._extract_symbol(data, symbol)
        return result

    def _extract_symbol(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Extract one symbol into a flat OHLCV DataFrame."""
        if isinstance(data.columns, pd.MultiIndex):
            level_values = list(data.columns.get_level_values(0).unique())
            lookup = {str(value).lower(): value for value in level_values}
            matched_symbol = lookup.get(symbol.lower())
            if matched_symbol is None:
                raise ValueError(f"Symbol {symbol} not in download result")
            df = data[matched_symbol].copy()
        else:
            fields = ["open", "high", "low", "close", "volume"]
            source_columns = {str(column).lower(): column for column in data.columns}
            cols = {
                field: data[source_column]
                for field in fields
                if (source_column := source_columns.get(field)) is not None
            }
            df = pd.DataFrame(cols, index=data.index)

        df.index = pd.to_datetime(df.index)
        df.index.name = "date"
        return df.dropna(how="all")

    def _last_trading_day(self) -> datetime:
        """Approximate last trading day without a holiday calendar."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if today.weekday() == 5:
            return today - timedelta(days=1)
        if today.weekday() == 6:
            return today - timedelta(days=2)
        return today

    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: BarSize = BarSize.DAILY,
    ) -> pd.DataFrame:
        """
        Return a MultiIndex (symbol, field) DataFrame for the requested range.

        Data is cached/fetched as daily bars and resampled to bar_size on the
        fly. Hourly data is intentionally unsupported upstream.
        """
        # Widen the fetch window so the cache is useful for future requests.
        fetch_start = min(start_date, _DEFAULT_HISTORY_START)
        fetch_end = self._last_trading_day()

        # Lockless pre-scan, followed by a locked double-check before fetching.
        probable_misses = [
            symbol for symbol in symbols
            if not self._cache_covers(symbol, fetch_start, fetch_end)
        ]

        if probable_misses:
            sorted_misses = sorted(set(probable_misses))
            locks = {symbol: _get_cache_lock(symbol) for symbol in sorted_misses}

            for symbol in sorted_misses:
                locks[symbol].acquire()
            try:
                confirmed_misses = [
                    symbol for symbol in sorted_misses
                    if not self._cache_covers(symbol, fetch_start, fetch_end)
                ]

                if confirmed_misses:
                    new_data = self._fetch_from_datafeed(confirmed_misses, fetch_start, fetch_end)

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
                for symbol in reversed(sorted_misses):
                    locks[symbol].release()

        frames: dict[tuple[str, str], pd.Series] = {}

        for symbol in symbols:
            symbol_data = self._read_cache(symbol)
            if symbol_data is None:
                raise ValueError(f"Cache miss after fetch for {symbol}")

            symbol_data = symbol_data.loc[
                (symbol_data.index >= pd.Timestamp(start_date))
                & (symbol_data.index <= pd.Timestamp(end_date))
            ]

            resampled = self._resample_symbol(symbol_data, bar_size)
            for field in ("open", "high", "low", "close", "volume"):
                if field in resampled.columns:
                    frames[(symbol, field)] = resampled[field]

        if not frames:
            raise ValueError(f"No data available for {symbols}")

        result = pd.DataFrame(frames)
        result.columns = pd.MultiIndex.from_tuples(result.columns)

        close_cols = [col for col in result.columns if col[1] == "close"]
        if close_cols:
            result = result.dropna(subset=close_cols, how="any")

        logger.info(
            "Returning %d bars for %s (%s to %s, bar_size=%s)",
            len(result),
            symbols,
            start_date.date(),
            end_date.date(),
            bar_size,
        )
        return result

    def _resample_symbol(self, data: pd.DataFrame, bar_size: BarSize) -> pd.DataFrame:
        """
        Resample daily bars to a coarser frequency.

        Uses manual grouping instead of pd.resample() so the output index is
        the last actual trading date in each period, not the calendar period end.
        """
        rule = _RESAMPLE_RULES.get(bar_size)
        if rule is None:
            return data

        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        agg = {field: method for field, method in agg.items() if field in data.columns}

        # Assign each daily row to a calendar period bucket and aggregate.
        periods = data.index.to_period(rule)
        grouped = data.groupby(periods)
        resampled = grouped.agg(agg).dropna(how="all")

        # Replace period-end dates with the last real trading date per group.
        real_dates = grouped.nth(-1).index
        resampled.index = pd.DatetimeIndex(real_dates, name=data.index.name)

        return resampled
