"""High-level data manager that handles all data fetching and storage.

Users just specify their universe and date range, and this handles:
- Checking what data already exists in the database
- Automatically pulling missing data from available sources
- Merging with existing data
- Fallback between sources (IBKR -> YFinance)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, List

import pandas as pd

from .database import Database
from .sources.base import BaseDataSource
from .sources.yfinance import YFinanceDataSource
from .sources.ibkr import IBKRDataSource


class DataManager:
    """High-level data manager with auto-pull capability and fallback sources.
    
    This is the main interface for users to get data. Just specify your universe
    and date range, and it handles all the downloading, storing, and merging.
    
    Example:
        manager = DataManager("db")
        
        # Just specify your universe - it handles everything
        data = manager.get_data(
            symbols=["AAPL", "GOOGL", "MSFT"],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
    """
    
    def __init__(
        self,
        storage_path: str = "db",
        enable_ibkr: bool = False,
        ibkr_host: str = "127.0.0.1",
        ibkr_port: int = 7497,
        enable_fallback: bool = True,
    ):
        """Initialize the DataManager.
        
        Args:
            storage_path: Path where database is stored
            enable_ibkr: Whether to try IBKR as a data source (requires TWS/gateway running)
            ibkr_host: IBKR host (default: 127.0.0.1)
            ibkr_port: IBKR port (default: 7497 for paper trading)
            enable_fallback: Whether to fall back to YFinance if IBKR fails
        """
        self.storage = Database(storage_path)
        self.logger = logging.getLogger(__name__)
        
        # Initialize data sources
        self.sources: List[tuple[BaseDataSource, str]] = []
        
        # Add IBKR if enabled
        if enable_ibkr:
            ibkr_source = IBKRDataSource(ibkr_host, ibkr_port)
            self.sources.append((ibkr_source, "IBKR"))
        
        # Add YFinance as fallback (or primary if IBKR not enabled)
        if enable_fallback:
            yf_source = YFinanceDataSource()
            if yf_source.is_available():
                self.sources.append((yf_source, "Yahoo Finance"))
        
        if not self.sources:
            raise ValueError("No data sources available. Install 'yfinance' for Yahoo Finance support.")
    
    def get_universe_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        auto_download: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Get data for a universe of symbols, auto-downloading if needed.
        
        This is the main method users should call. It:
        - Checks what data exists in the database
        - Auto-downloads missing data or gaps in date ranges
        - Returns a dict of symbol -> DataFrame for all requested symbols
        
        Args:
            symbols: List of symbols to fetch
            start_date: Start date for data
            end_date: End date for data
            auto_download: If True, automatically download missing data from sources
            
        Returns:
            Dictionary mapping symbol to DataFrame with OHLCV data
            
        Example:
            data = manager.get_universe_data(
                symbols=["AAPL", "GOOGL"],
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31)
            )
        """
        if auto_download:
            self._ensure_data_available(symbols, start_date, end_date)
        
        # Load data for all symbols
        result = {}
        for symbol in symbols:
            df = self._load_symbol_data(symbol, start_date, end_date)
            if df is not None and not df.empty:
                result[symbol] = df
            else:
                self.logger.warning(f"No data available for {symbol}")
        
        return result
    
    def _ensure_data_available(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Ensure data is available for all symbols, downloading if needed."""
        for symbol in symbols:
            if self._needs_download(symbol, start_date, end_date):
                self.logger.info(f"Need to download data for {symbol}")
                self._download_symbol_data(symbol, start_date, end_date)
    
    def _needs_download(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> bool:
        """Check if we need to download data for a symbol.
        
        Returns True if:
        - Symbol doesn't exist in database
        - Date range has gaps (missing earlier or later dates)
        """
        existing_data = self.storage.load_daily_data(symbol)
        
        if existing_data is None or existing_data.empty:
            return True
        
        existing_start = existing_data.index.min().to_pydatetime()
        existing_end = existing_data.index.max().to_pydatetime()
        
        # Check if we have data before start_date or after end_date
        needs_earlier = existing_start > start_date
        needs_later = existing_end < end_date
        
        if needs_earlier:
            self.logger.info(f"{symbol}: Need earlier data ({existing_start} > {start_date})")
        
        if needs_later:
            self.logger.info(f"{symbol}: Need later data ({existing_end} < {end_date})")
        
        return needs_earlier or needs_later
    
    def _download_symbol_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> bool:
        """Download data for a symbol from available sources."""
        for source, source_name in self.sources:
            try:
                if not source.is_available():
                    self.logger.debug(f"{source_name} is not available, trying next source")
                    continue
                
                self.logger.info(f"Downloading {symbol} from {source_name}")
                
                # Try to pull from this source
                data = source.pull_historical_data(symbol, start_date, end_date)
                
                if data is not None and not data.empty:
                    # Save to database
                    self.storage.save_daily_data(symbol, data)
                    self.logger.info(f"Successfully downloaded and saved {len(data)} bars for {symbol} from {source_name}")
                    return True
                
            except Exception as e:
                self.logger.warning(f"Error downloading {symbol} from {source_name}: {e}")
                continue
        
        self.logger.error(f"Failed to download data for {symbol} from any source")
        return False
    
    def _load_symbol_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[pd.DataFrame]:
        """Load data for a symbol from database, filtered to date range."""
        data = self.storage.load_daily_data(symbol)
        
        if data is None or data.empty:
            return None
        
        # Filter to requested date range
        mask = (data.index >= pd.Timestamp(start_date)) & (data.index <= pd.Timestamp(end_date))
        filtered = data[mask]
        
        return filtered if not filtered.empty else None
    
    def get_available_symbols(self) -> List[str]:
        """Get list of symbols available in the database."""
        return self.storage.get_available_symbols()
    
    def get_database_stats(self) -> dict:
        """Get database statistics."""
        return self.storage.get_stats()

