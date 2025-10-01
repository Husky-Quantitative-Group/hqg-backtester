"""Yahoo Finance data source implementation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from .base import BaseDataSource


class YFinanceDataSource(BaseDataSource):
    """Yahoo Finance data source with normalized output."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._yfinance_available = None
    
    def is_available(self) -> bool:
        """Check if yfinance is available."""
        if self._yfinance_available is None:
            try:
                import yfinance as yf
                self._yfinance_available = True
            except ImportError:
                self.logger.warning("yfinance not installed")
                self._yfinance_available = False
        return self._yfinance_available
    
    def pull_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> Optional[pd.DataFrame]:
        """Pull historical data from Yahoo Finance.
        
        Args:
            symbol: Symbol to fetch
            start_date: Start date
            end_date: End date
            **kwargs: Additional yfinance parameters
            
        Returns:
            Normalized DataFrame with OHLCV data or None if failed
        """
        if not self.is_available():
            return None
        
        try:
            import yfinance as yf
            
            self.logger.info(f"Fetching {symbol} from Yahoo Finance ({start_date.date()} to {end_date.date()})")
            
            # Download data
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval='1d',
                auto_adjust=True,  # Use adjusted prices
                actions=False,  # Don't include dividends/splits
            )
            
            if df is None or df.empty:
                self.logger.warning(f"No data returned from Yahoo Finance for {symbol}")
                return None
            
            # Normalize the DataFrame
            df = self.normalize_dataframe(df)
            
            self.logger.info(f"Successfully fetched {len(df)} bars for {symbol} from Yahoo Finance")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching data from Yahoo Finance for {symbol}: {e}")
            return None
