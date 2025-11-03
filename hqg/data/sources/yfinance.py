"""Yahoo Finance data source implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from .base import BaseDataSource


class YFinanceDataSource(BaseDataSource):
    """Yahoo Finance data source with normalized output."""
    
    def __init__(self):
        self._yfinance_available = None
    
    def is_available(self) -> bool:
        """Check if yfinance is available."""
        if self._yfinance_available is None:
            try:
                import yfinance as yf
                self._yfinance_available = True
            except ImportError:
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
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval='1d',
                auto_adjust=True,  
                actions=False,  
            )
            
            if df is None or df.empty:
                return None
            
            return self.normalize_dataframe(df)
            
        except Exception as e:
            return None
