"""Data feed for providing synchronized market data to the backtester."""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Dict, Iterator, List, Tuple

import pandas as pd

from .sources.ibkr import DataManager
from ..types import Slice, TradeBar


class DataFeed:
    """Data feed that provides synchronized market data slices."""
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
        # Market hours (NYSE: 9:30 AM - 4:00 PM EST)
        self.market_open = time(9, 30)
        self.market_close = time(16, 0)
    
    def create_feed(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        auto_pull: bool = True,
    ) -> Iterator[Tuple[datetime, Dict[str, TradeBar]]]:
        """Create a data feed iterator for the backtester."""
        # Get synchronized data
        data = self.data_manager.get_synchronized_bars(symbols, start_date, end_date, auto_pull)
        
        if data.empty:
            self.logger.warning("No data available for feed")
            return
        
        # Filter for trading days only
        trading_data = self._filter_trading_days(data)
        
        # Create iterator
        for timestamp, row in trading_data.iterrows():
            bars = {}
            
            for symbol in symbols:
                if (symbol, "open") in row.index:
                    try:
                        bar = TradeBar(
                            symbol=symbol,
                            end_time=timestamp,
                            open=float(row[(symbol, "open")]),
                            high=float(row[(symbol, "high")]),
                            low=float(row[(symbol, "low")]),
                            close=float(row[(symbol, "close")]),
                            volume=float(row[(symbol, "volume")]),
                        )
                        bars[symbol] = bar
                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"Error creating bar for {symbol} at {timestamp}: {e}")
                        continue
            
            if bars:  # Only yield if we have valid bars
                yield timestamp, bars
    
    def _filter_trading_days(self, data: pd.DataFrame) -> pd.DataFrame:
        """Filter data to include only trading days and market hours."""
        # Filter out weekends (Saturday=5, Sunday=6)
        trading_days = data[data.index.dayofweek < 5]
        
        # Filter for market hours (9:30 AM - 4:00 PM)
        market_hours = trading_days[
            (trading_days.index.time >= self.market_open) & 
            (trading_days.index.time <= self.market_close)
        ]
        
        self.logger.info(f"Filtered {len(data)} bars to {len(market_hours)} trading bars")
        
        return market_hours
    
    def get_data_summary(self, symbols: List[str], start_date: datetime, end_date: datetime) -> Dict:
        """Get summary of available data."""
        data = self.data_manager.get_data(symbols, start_date, end_date, auto_pull=False)
        
        summary = {
            "symbols": symbols,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "available_symbols": [],
            "missing_symbols": [],
            "data_points": {},
        }
        
        for symbol in symbols:
            if symbol in data:
                df = data[symbol]
                summary["available_symbols"].append(symbol)
                summary["data_points"][symbol] = len(df)
            else:
                summary["missing_symbols"].append(symbol)
        
        return summary
