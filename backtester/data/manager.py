from datetime import datetime

import pandas as pd

from .database import Database
from .sources.base import BaseDataSource
from .sources.yfinance import YFinanceDataSource


class DataManager:
    def __init__(
        self,
        storage_path=None,
        enable_ibkr=False,
        ibkr_host="127.0.0.1",
        ibkr_port=7497,
        enable_fallback=True,
    ):
        if storage_path is None:
            self.storage = Database()
        else:
            self.storage = Database(storage_path)
        
        self.sources = []
        
        if enable_ibkr:
            from .sources.ibkr import IBKRDataSource
            ibkr_source = IBKRDataSource(ibkr_host, ibkr_port)
            self.sources.append((ibkr_source, "IBKR"))
        
        if enable_fallback:
            yf_source = YFinanceDataSource()
            if yf_source.is_available():
                self.sources.append((yf_source, "Yahoo Finance"))
        
        if not self.sources:
            raise ValueError("No data sources available. Install 'yfinance' for Yahoo Finance support.")
    
    def get_universe_data(
        self,
        symbols,
        start_date,
        end_date,
        auto_download=True,
    ):
        if auto_download:
            self._ensure_data_available(symbols, start_date, end_date)
        
        result = {}
        for symbol in symbols:
            df = self._load_symbol_data(symbol, start_date, end_date)
            if df is not None and not df.empty:
                result[symbol] = df
        
        return result
    
    def _ensure_data_available(self, symbols, start_date, end_date):
        for symbol in symbols:
            if self._needs_download(symbol, start_date, end_date):
                print(f"Downloading {symbol} data from {start_date.date()} to {end_date.date()}...")
                success = self._download_symbol_data(symbol, start_date, end_date)
                if success:
                    print(f"Successfully downloaded {symbol} data")
                else:
                    print(f"Failed to download {symbol} data")
    
    def _needs_download(self, symbol, start_date, end_date):
        existing_data = self.storage.load_daily_data(symbol)
        
        if existing_data is None or existing_data.empty:
            return True
        
        existing_start = existing_data.index.min().to_pydatetime()
        existing_end = existing_data.index.max().to_pydatetime()
        
        needs_earlier = existing_start > start_date
        needs_later = existing_end < end_date
        
        return needs_earlier or needs_later
    
    def _download_symbol_data(self, symbol, start_date, end_date):
        for source, source_name in self.sources:
            try:
                if not source.is_available():
                    continue
                
                data = source.pull_historical_data(symbol, start_date, end_date)
                
                if data is not None and not data.empty:
                    self.storage.save_daily_data(symbol, data)
                    print(f"Saved {len(data)} days of {symbol} data to database")
                    return True
                
            except Exception as e:
                print(f"{source_name} failed for {symbol}: {str(e)}")
                continue
        return False
    
    def _load_symbol_data(self, symbol, start_date, end_date):
        data = self.storage.load_daily_data(symbol)
        
        if data is None or data.empty:
            return None
        
        mask = (data.index >= pd.Timestamp(start_date)) & (data.index <= pd.Timestamp(end_date))
        filtered = data[mask]
        
        return filtered if not filtered.empty else None
    
    def get_available_symbols(self):
        return self.storage.get_available_symbols()
    
    def get_database_stats(self):
        return self.storage.get_stats()

