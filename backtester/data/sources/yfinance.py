from datetime import datetime

import pandas as pd

from .base import BaseDataSource


class YFinanceDataSource(BaseDataSource):
    def __init__(self):
        self._yfinance_available = None
    
    def is_available(self):
        if self._yfinance_available is None:
            try:
                import yfinance as yf
                self._yfinance_available = True
            except ImportError:
                self._yfinance_available = False
        return self._yfinance_available
    
    def pull_historical_data(self, symbol, start_date, end_date, **kwargs):
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
            # Log the error for debugging but don't expose it
            print(f"YFinance download error for {symbol}: {str(e)[:100]}")
            return None
