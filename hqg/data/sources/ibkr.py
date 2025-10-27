"""Interactive Brokers data source implementation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from .base import BaseDataSource


def _try_import_ibkr():
    """Try to import ib_insync, return None if not available."""
    try:
        from ib_insync import IB, Contract, Forex, Stock, util
        return IB, Contract, Forex, Stock, util
    except ImportError:
        return None


class IBKRDataSource(BaseDataSource):
    """Interactive Brokers data source."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497):
        self.host = host
        self.port = port
        self.ib = None
        self.logger = logging.getLogger(__name__)
        self._ibkr_available = None
    
    def is_available(self) -> bool:
        """Check if IBKR is available."""
        if self._ibkr_available is not None:
            return self._ibkr_available
        
        # Try to import ib_insync
        ibkr_mod = _try_import_ibkr()
        if ibkr_mod is None:
            self._ibkr_available = False
            return False
        
        IB, _, _, _, _ = ibkr_mod
        
        # Try to connect
        try:
            self.ib = IB()
            self.ib.connect(self.host, self.port, clientId=1, timeout=5)
            self._ibkr_available = True
            self.logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.debug(f"IBKR not available: {e}")
            self._ibkr_available = False
            return False
    
    def pull_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> Optional[pd.DataFrame]:
        """Pull historical data from IBKR."""
        if not self.is_available():
            return None
        
        ibkr_mod = _try_import_ibkr()
        if ibkr_mod is None:
            return None
        
        IB, Contract, Stock, _, util = ibkr_mod
        
        try:
            # Create contract
            contract = Stock(symbol, "SMART", "USD")
            
            # Determine duration needed
            duration_days = (end_date - start_date).days
            if duration_days <= 30:
                duration_str = "1 M"
            elif duration_days <= 365:
                duration_str = "1 Y"
            else:
                duration_str = "2 Y"
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,  # UTC
            )
            
            if not bars:
                self.logger.warning(f"No data returned for {symbol}")
                return None
            
            # Convert to DataFrame
            df = util.df(bars)
            
            # Rename date column
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'timestamp'})
            elif 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'timestamp'})
            
            # Set timestamp as index
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            # Normalize using base class method
            df = self.normalize_dataframe(df)
            
            # Filter by date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            
            self.logger.info(f"Pulled {len(df)} bars for {symbol} from IBKR")
            return df
            
        except Exception as e:
            self.logger.error(f"Error pulling data for {symbol}: {e}")
            return None

