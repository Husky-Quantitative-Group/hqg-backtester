import threading
from hqg_algorithms import BarSize
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List
import logging
from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)

# yf.download() is not thread-safe, concurrent calls corrupt shared internal
_yfinance_lock = threading.Lock()

_RESAMPLE_RULES = {
    BarSize.DAILY: None,
    BarSize.WEEKLY: "W-FRI",
    BarSize.MONTHLY: "M",
    BarSize.QUARTERLY: "Q",
}

class YFDataProvider(BaseDataProvider):

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

        Data is always fetched as daily bars and resampled to
        bar_size on the fly.
        """

        df = self._fetch_from_yf(symbols, start_date, end_date)

        frames: dict[tuple[str, str], pd.Series] = {}

        for symbol in symbols:
            sym_df = df[symbol]
            # resample if needed
            sym_df = self._resample(sym_df, bar_size)

            for field in ("open", "high", "low", "close", "volume"):
                if field in sym_df.columns:
                    frames[(symbol, field)] = sym_df[field]

        if not frames:
            raise ValueError(f"No data available for {symbols}")

        result = pd.DataFrame(frames)
        #result.columns = pd.MultiIndex.from_tuples(result.columns)

        # Mixed calendars (e.g., BTC-USD trades on holidays/weekends while equities do not)
        # can create rows with missing closes for a subset of symbols. Those rows break
        # portfolio valuation downstream, so keep only bars where all symbol closes exist.
        close_cols = [col for col in result.columns if col[1] == "close"]
        if close_cols:
            result = result.dropna(subset=close_cols, how="any")

        logger.info(
            f"Returning {len(result)} bars for {symbols} "
            f"({start_date.date()} to {end_date.date()}, bar_size={bar_size})"
        )
        return result
    

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

        with _yfinance_lock:
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
        if bar_size not in _RESAMPLE_RULES:
            raise ValueError(
                f"yfinance only supports daily or coarser bars. "
                f"Got {bar_size}. Supported: {list(_RESAMPLE_RULES)}"
            )
        rule = _RESAMPLE_RULES[bar_size]
        if rule is None:  # DAILY, no resample needed
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
        real_dates = grouped.nth(-1).index
        resampled.index = pd.DatetimeIndex(real_dates, name=df.index.name)

        return resampled
