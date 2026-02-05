import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import logging
from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"


class YFDataProvider(BaseDataProvider):
    """
    Fetches historical market data using yfinance.
    Caches daily data as parquet files (one per ticker) to avoid redundant API calls.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: timedelta = timedelta(days=1),
    ) -> pd.DataFrame:
        symbols = [s.upper() for s in symbols]
        interval = self._get_yfinance_interval(bar_size)
        is_daily = interval == "1d"

        logger.info(f"Fetching data for {symbols} from {start_date} to {end_date}")

        frames = {}
        for symbol in symbols:
            if is_daily:
                df = self._get_cached(symbol, start_date, end_date)
            else:
                df = self._fetch_symbol(symbol, start_date, end_date, interval)
            if df is not None and not df.empty:
                frames[symbol] = df

        if not frames:
            raise ValueError(f"No data found for symbols {symbols}")

        formatted = self._build_multiindex(frames)

        if formatted.empty:
            raise ValueError("Formatted data is empty")

        logger.info(f"Fetched {len(formatted)} bars for {list(frames.keys())}")
        return formatted

    # ── cache logic ──────────────────────────────────────────────

    def _cache_path(self, symbol: str) -> Path:
        return self.cache_dir / f"{symbol}.parquet"

    def _get_cached(self, symbol: str, start: datetime, end: datetime) -> Optional[pd.DataFrame]:
        """Return daily OHLCV for symbol, fetching/extending cache as needed."""
        path = self._cache_path(symbol)

        if path.exists():
            cached = pd.read_parquet(path)
            cached.index = pd.to_datetime(cached.index)
            cached_start = cached.index.min()
            cached_end = cached.index.max()

            need_before = start.date() < cached_start.date()
            need_after = end.date() > cached_end.date()

            if need_before or need_after:
                parts = [cached]

                if need_before:
                    before = self._fetch_symbol(symbol, start, cached_start - timedelta(days=1), "1d")
                    if before is not None and not before.empty:
                        parts.append(before)

                if need_after:
                    after = self._fetch_symbol(symbol, cached_end + timedelta(days=1), end, "1d")
                    if after is not None and not after.empty:
                        parts.append(after)

                cached = pd.concat(parts).sort_index()
                cached = cached[~cached.index.duplicated(keep="last")]
                cached.to_parquet(path)

        else:
            cached = self._fetch_symbol(symbol, start, end, "1d")
            if cached is None or cached.empty:
                return None
            cached.to_parquet(path)

        # filter to requested range
        mask = (cached.index >= pd.Timestamp(start)) & (cached.index <= pd.Timestamp(end))
        return cached.loc[mask]

    # ── yfinance fetch ───────────────────────────────────────────

    def _fetch_symbol(
        self, symbol: str, start: datetime, end: datetime, interval: str
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV for a single symbol from yfinance."""
        try:
            data = yf.download(
                tickers=symbol,
                start=start,
                end=end + timedelta(days=1),
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
            if data.empty:
                return None

            # yfinance single-ticker download may have MultiIndex columns with ticker level
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel("Ticker")

            data.columns = [c.lower() for c in data.columns]
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch {symbol}: {e}")
            return None

    # ── formatting ───────────────────────────────────────────────

    def _build_multiindex(self, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Combine per-symbol DataFrames into a single MultiIndex DataFrame."""
        formatted = pd.DataFrame()
        for symbol, df in frames.items():
            for field in ["open", "high", "low", "close", "volume"]:
                if field in df.columns:
                    formatted[(symbol, field)] = df[field]

        if len(formatted.columns) > 0 and not isinstance(formatted.columns, pd.MultiIndex):
            formatted.columns = pd.MultiIndex.from_tuples(formatted.columns)

        return formatted

    def _get_yfinance_interval(self, bar_size: timedelta) -> str:
        total_minutes = int(bar_size.total_seconds() / 60)
        intervals = {
            1: "1m", 5: "5m", 15: "15m", 30: "30m",
            60: "1h", 1440: "1d", 10080: "1wk",
        }
        if total_minutes in intervals:
            return intervals[total_minutes]
        if total_minutes >= 43200:
            return "1mo"
        raise ValueError(f"Unsupported bar size: {bar_size}")
