"""Interactive Brokers data source implementation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from ib_insync import IB, Contract, Forex, Stock, util

from ..storage import LocalStorage
from .base import BaseDataSource
from .yfinance import YFinanceDataSource


class IBKRDataSource(BaseDataSource):
    """Interactive Brokers data source with auto-pull capability."""
    
    def __init__(self, storage: LocalStorage, host: str = "127.0.0.1", port: int = 7497):
        self.storage = storage
        self.host = host
        self.port = port
        self.ib = None
        self.logger = logging.getLogger(__name__)
        
        # IBKR commission rates (simplified)
        self.commission_rates = {
            "STK": 0.005,  # $0.005 per share
            "FOREX": 0.00002,  # 0.00002 per unit (0.002%)
            "FUT": 2.0,  # $2.0 per contract
        }
    
    def is_available(self) -> bool:
        """Check if IBKR is available."""
        if self.ib and self.ib.isConnected():
            return True
        return self.connect()
    
    def connect(self) -> bool:
        """Connect to Interactive Brokers TWS or Gateway."""
        try:
            self.ib = IB()
            self.ib.connect(self.host, self.port, clientId=1)
            self.logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to IBKR: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Interactive Brokers."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.logger.info("Disconnected from IBKR")
    
    def _get_contract(self, symbol: str, sec_type: str = "STK") -> Contract:
        """Create IBKR contract for a symbol."""
        if sec_type == "STK":
            # US Stock
            contract = Stock(symbol, "SMART", "USD")
        elif sec_type == "FOREX":
            # Forex pair
            contract = Forex(symbol)
        else:
            raise ValueError(f"Unsupported security type: {sec_type}")
        
        return contract
    
    def pull_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        sec_type: str = "STK",
        duration_str: str = "1 Y",
        bar_size: str = "1 day",
    ) -> Optional[pd.DataFrame]:
        """Pull historical data from IBKR."""
        if not self.ib or not self.ib.isConnected():
            if not self.connect():
                return None
        
        try:
            # Create contract
            contract = self._get_contract(symbol, sec_type)
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,  # UTC
            )
            
            if not bars:
                self.logger.warning(f"No data returned for {symbol}")
                return None
            
            # Convert to DataFrame
            df = util.df(bars)
            
            # Clean up DataFrame
            df = df.rename(columns={
                "date": "timestamp",
            })
            
            # Set timestamp as index
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            
            # Normalize using base class method
            df = self.normalize_dataframe(df)
            
            # Filter by date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            
            # Sort by timestamp
            df = df.sort_index()
            
            self.logger.info(f"Pulled {len(df)} bars for {symbol}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error pulling data for {symbol}: {e}")
            return None
    
    def auto_pull_symbol(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        sec_type: str = "STK",
    ) -> bool:
        """Automatically pull and store data for a new symbol."""
        if self.storage.symbol_exists(symbol):
            self.logger.info(f"Symbol {symbol} already exists, skipping pull")
            return True
        
        self.logger.info(f"Auto-pulling data for {symbol}")
        
        # Pull historical data
        data = self.pull_historical_data(symbol, start_date, end_date, sec_type)
        
        if data is None or data.empty:
            self.logger.error(f"Failed to pull data for {symbol}")
            return False
        
        # Store data
        try:
            self.storage.save_daily_data(symbol, data)
            self.logger.info(f"Successfully stored data for {symbol}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store data for {symbol}: {e}")
            return False
    
    def get_commission_rate(self, symbol: str, sec_type: str = "STK") -> float:
        """Get commission rate for a symbol."""
        return self.commission_rates.get(sec_type, 0.005)
    
    def calculate_commission(
        self,
        symbol: str,
        quantity: int,
        price: float,
        sec_type: str = "STK",
    ) -> float:
        """Calculate commission for a trade."""
        rate = self.get_commission_rate(symbol, sec_type)
        
        if sec_type == "STK":
            # $0.005 per share, minimum $1.00, maximum 1% of trade value
            commission = max(1.0, min(quantity * rate, 0.01 * quantity * price))
        elif sec_type == "FOREX":
            # 0.00002 per unit
            commission = quantity * price * rate
        elif sec_type == "FUT":
            # $2.0 per contract
            commission = quantity * rate
        else:
            commission = quantity * rate
        
        return round(commission, 2)


class DataManager:
    """High-level data manager with auto-pull capability and fallback sources."""
    
    def __init__(self, storage_path: str, ibkr_host: str = "127.0.0.1", ibkr_port: int = 7497, enable_fallback: bool = True):
        self.storage = LocalStorage(storage_path)
        self.ibkr_source = IBKRDataSource(self.storage, ibkr_host, ibkr_port)
        self.yfinance_source = YFinanceDataSource() if enable_fallback else None
        self.enable_fallback = enable_fallback
        self.logger = logging.getLogger(__name__)
    
    def _try_pull_from_source(
        self,
        source: BaseDataSource,
        source_name: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        """Try to pull data from a specific source.
        
        Args:
            source: Data source instance
            source_name: Name of the source (for logging)
            symbol: Symbol to fetch
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with data or None if failed
        """
        try:
            if not source.is_available():
                self.logger.warning(f"{source_name} is not available")
                return None
            
            data = source.pull_historical_data(symbol, start_date, end_date)
            if data is not None and not data.empty:
                self.logger.info(f"Successfully pulled {len(data)} bars for {symbol} from {source_name}")
                return data
            else:
                self.logger.warning(f"{source_name} returned no data for {symbol}")
                return None
        except Exception as e:
            self.logger.error(f"Error pulling from {source_name} for {symbol}: {e}")
            return None
    
    def auto_pull_symbol(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> bool:
        """Automatically pull and store data for a symbol with fallback support.
        
        Tries sources in order: IBKR -> YFinance (if enabled)
        
        Args:
            symbol: Symbol to fetch
            start_date: Start date
            end_date: End date
            
        Returns:
            True if data was successfully pulled and stored
        """
        # Check if we already have data for this date range
        existing_data = self.storage.load_daily_data(symbol)
        if existing_data is not None and not existing_data.empty:
            # Check if we have complete coverage
            existing_range = (existing_data.index.min(), existing_data.index.max())
            if existing_range[0] <= pd.Timestamp(start_date) and existing_range[1] >= pd.Timestamp(end_date):
                self.logger.info(f"Symbol {symbol} already has data for requested range, skipping pull")
                return True
        
        self.logger.info(f"Auto-pulling data for {symbol}")
        
        data = None
        
        # Try IBKR first
        data = self._try_pull_from_source(
            self.ibkr_source,
            "IBKR",
            symbol,
            start_date,
            end_date,
        )
        
        # Fallback to YFinance if IBKR failed
        if data is None and self.enable_fallback and self.yfinance_source:
            self.logger.info(f"Falling back to Yahoo Finance for {symbol}")
            data = self._try_pull_from_source(
                self.yfinance_source,
                "Yahoo Finance",
                symbol,
                start_date,
                end_date,
            )
        
        if data is None or data.empty:
            self.logger.error(f"Failed to pull data for {symbol} from any source")
            return False
        
        # Store data (merge with existing to avoid duplicates)
        try:
            self.storage.save_daily_data(symbol, data, merge=True)
            self.logger.info(f"Successfully stored data for {symbol}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store data for {symbol}: {e}")
            return False
    
    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        auto_pull: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Get data for multiple symbols, auto-pulling if needed."""
        # Auto-pull missing or incomplete symbols if requested
        if auto_pull:
            for symbol in symbols:
                existing_data = self.storage.load_daily_data(symbol)
                needs_pull = False
                
                if existing_data is None or existing_data.empty:
                    needs_pull = True
                else:
                    # Check if we have complete coverage for the date range
                    existing_range = (existing_data.index.min(), existing_data.index.max())
                    if existing_range[0] > pd.Timestamp(start_date) or existing_range[1] < pd.Timestamp(end_date):
                        needs_pull = True
                
                if needs_pull:
                    self.logger.info(f"Auto-pulling {symbol}")
                    self.auto_pull_symbol(symbol, start_date, end_date)
        
        # Load data for all symbols
        data = {}
        for symbol in symbols:
            df = self.storage.load_daily_data(symbol)
            if df is not None:
                # Filter by date range
                df = df[(df.index >= start_date) & (df.index <= end_date)]
                if not df.empty:
                    data[symbol] = df
                else:
                    self.logger.warning(f"No data available for {symbol} in date range")
            else:
                self.logger.warning(f"No data found for {symbol}")
        
        return data
    
    def get_synchronized_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        auto_pull: bool = True,
    ) -> pd.DataFrame:
        """Get synchronized OHLCV data for multiple symbols."""
        data = self.get_data(symbols, start_date, end_date, auto_pull)
        
        if not data:
            return pd.DataFrame()
        
        # Create MultiIndex DataFrame with symbol as level 1
        dfs = []
        for symbol, df in data.items():
            df = df.copy()
            df.columns = pd.MultiIndex.from_product([[symbol], df.columns])
            dfs.append(df)
        
        # Concatenate all DataFrames
        combined = pd.concat(dfs, axis=1)
        
        # Sort by date
        combined = combined.sort_index()
        
        return combined
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols."""
        return sorted(list(self.storage.get_available_symbols()))
    
    def get_storage_info(self) -> Dict:
        """Get storage information."""
        return self.storage.get_storage_info()
