"""Base data source interface for normalized data ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import pandas as pd


class BaseDataSource(ABC):
    """Abstract base class for data sources.
    
    All data sources must return data in the normalized format:
    - Index: DatetimeIndex (timezone-aware UTC or naive)
    - Columns: open, high, low, close, volume (lowercase)
    - Types: float64 for OHLC, int64 for volume
    """
    
    @abstractmethod
    def pull_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> Optional[pd.DataFrame]:
        """Pull historical OHLCV data for a symbol.
        
        Args:
            symbol: Symbol to fetch
            start_date: Start date
            end_date: End date
            **kwargs: Source-specific parameters
            
        Returns:
            DataFrame with normalized OHLCV data or None if failed
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the data source is available/reachable.
        
        Returns:
            True if source can be used, False otherwise
        """
        pass
    
    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize a DataFrame to the standard format.
        
        Args:
            df: Input DataFrame with OHLCV data
            
        Returns:
            Normalized DataFrame
        """
        # Ensure index is DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'date' in df.columns:
                df = df.set_index('date')
            elif 'timestamp' in df.columns:
                df = df.set_index('timestamp')
            df.index = pd.to_datetime(df.index)
        
        # Convert timezone-aware to timezone-naive (UTC)
        if df.index.tz is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)
        
        # Normalize column names to lowercase
        df.columns = df.columns.str.lower()
        
        # Ensure required columns exist
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Select only required columns
        df = df[required_columns].copy()
        
        # Convert types
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(int)
        
        # Remove duplicates
        df = df[~df.index.duplicated(keep='last')]
        
        # Sort by date
        df = df.sort_index()
        
        # Remove rows with NaN values
        df = df.dropna()
        
        return df
