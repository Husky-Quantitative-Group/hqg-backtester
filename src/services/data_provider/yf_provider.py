import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List
import logging
from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class YFDataProvider(BaseDataProvider):
    """
    Fetches historical market data using yfinance.
    Returns data in the format expected by the backtester.
    """
    
    def get_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        bar_size: timedelta = timedelta(days=1)
    ) -> pd.DataFrame:
        """
        Fetch historical data for given symbols.
        
        Args:
            symbols: List of ticker symbols
            start_date: Start date for data
            end_date: End date for data
            bar_size: Bar size (default: 1 day)
            
        Returns:
            MultiIndex DataFrame with (timestamp, (symbol, field)) structure
        """
        symbols = [s.upper() for s in symbols]

        logger.info(f"Fetching data for {symbols} from {start_date} to {end_date}")
        
        # get interval based on bar_size
        interval = self._get_yfinance_interval(bar_size)
        
        # fetch data for all symbols
        # Note: yfinance download is synchronous, but we're in async context
        data = yf.download(
            tickers=symbols,
            start=start_date,
            end=end_date + timedelta(days=1),  # include end date
            interval=interval,
            progress=False,
            group_by='ticker',
            auto_adjust=True
        )
        
        if data.empty:
            raise ValueError(f"No data found for symbols {symbols}")
        
        # match expected format
        formatted_data = self._format_data(data, symbols)

        if formatted_data.empty:
            raise ValueError("Formatted data is empty")
        
        logger.info(f"Fetched {len(formatted_data)} bars")
        
        return formatted_data
    
    def _get_yfinance_interval(self, bar_size: timedelta) -> str:
        """Convert timedelta to yfinance interval string."""
        total_minutes = int(bar_size.total_seconds() / 60)
        
        if total_minutes == 1:
            return "1m"
        elif total_minutes == 5:
            return "5m"
        elif total_minutes == 15:
            return "15m"
        elif total_minutes == 30:
            return "30m"
        elif total_minutes == 60:
            return "1h"
        elif total_minutes == 1440:  # 1 day
            return "1d"
        elif total_minutes == 10080:  # 1 week
            return "1wk"
        elif total_minutes >= 43200:  # 1 month
            return "1mo"
        else:
            raise ValueError(f"Unsupported bar size: {bar_size}")
    
    def _format_data(self, data: pd.DataFrame, symbols: List[str]) -> pd.DataFrame:
        """ Expected format: MultiIndex columns with (symbol, field) where field is one of: open, high, low, close, volume """
        formatted = pd.DataFrame()
        
        for symbol in symbols:
            if symbol in data.columns:
                for field in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if field in data[symbol].columns:
                        formatted[(symbol, field.lower())] = data[symbol][field]
        
        # ensure MultiIndex columns
        if len(formatted.columns) > 0 and not isinstance(formatted.columns, pd.MultiIndex):
            formatted.columns = pd.MultiIndex.from_tuples(formatted.columns)
        
        return formatted