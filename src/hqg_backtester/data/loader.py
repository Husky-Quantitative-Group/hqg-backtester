"""Data loader module for the backtester."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from .types import Slice, TradeBar
from .storage import LocalStorage


class DataLoader:
    """Base data loader class.

    This loader can be constructed with either a filesystem path (str/Path)
    or a LocalStorage instance. It returns a mapping of symbol -> DataFrame
    filtered to the requested date range.
    """

    def __init__(self, data_path: Union[str, Path, LocalStorage] = "data"):
        """Initialize the data loader.
        
        Args:
            data_path: Path to data directory or a LocalStorage instance
        """
        if isinstance(data_path, LocalStorage):
            self.storage = data_path
        else:
            self.storage = LocalStorage(data_path)

        self.data_path = self.storage.base_path
        self.logger = logging.getLogger("DataLoader")
        
    def load_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Load data for the given symbol between start and end dates.
        
        Args:
            symbol: Symbol to load
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data or None if not available
        """
        self.logger.info(f"Loading data for {symbol} from {start_date} to {end_date}")

        df = self.storage.load_daily_data(symbol)
        if df is None or df.empty:
            return None

        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Normalize timezone: convert timezone-aware to timezone-naive (UTC)
        if df.index.tz is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)

        # Ensure start_date and end_date are also timezone-naive
        if start_date is not None:
            start_ts = pd.Timestamp(start_date).tz_localize(None) if pd.Timestamp(start_date).tz is None else pd.Timestamp(start_date).tz_convert('UTC').tz_localize(None)
            df = df.loc[df.index >= start_ts]
        if end_date is not None:
            end_ts = pd.Timestamp(end_date).tz_localize(None) if pd.Timestamp(end_date).tz is None else pd.Timestamp(end_date).tz_convert('UTC').tz_localize(None)
            df = df.loc[df.index <= end_ts]

        if df.empty:
            return None

        return df
        
    def get_next_slice(self) -> Optional[Slice]:
        """Get the next data slice.
        
        Returns:
            Data slice or None if no more data
        """
        # Not implemented for file-based loader
        return None