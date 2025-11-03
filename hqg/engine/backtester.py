"""Simple backtester for quantitative strategies."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Type

from ..api import Algorithm
from ..analysis.metrics import PerformanceMetrics
from ..data.manager import DataManager
from ..execution.broker import IBBroker
from ..types import Slice, TradeBar

import pandas as pd



class Backtester:
    """Simple backtester for quantitative strategies."""

    def __init__(self, 
                 data_path: str | Path = "db",
                 algorithm_class: Type[Algorithm] = None,
                 initial_cash: float = 100_000.0,
                 commission_rate: float = 0.005):
        """Initialize the backtester."""
        self.data_path = Path(data_path)
        self.algorithm_class = algorithm_class
        self.initial_cash = initial_cash
        

        
        # Initialize components
        self.data_manager = DataManager(str(self.data_path))
        self.broker = IBBroker(commission_rate=commission_rate)
        self.performance_metrics = PerformanceMetrics()
        
        # Runtime state
        self.algorithm = None
        self.equity_curve = []

    def run_backtest(self, 
                    start_date: datetime,
                    end_date: datetime,
                    symbols: List[str]) -> Dict[str, Any]:
        """Run the backtest."""
        
        # Get data for all symbols (auto-download if needed)
        data_cache = self.data_manager.get_universe_data(symbols, start_date, end_date, auto_download=True)
        
        if not data_cache:
            raise ValueError("No data available for any symbols")
        
        available_symbols = list(data_cache.keys())
        if len(available_symbols) < len(symbols):
            missing = set(symbols) - set(available_symbols)
            print(f"Warning: Could not get data for: {missing}")
        
        # Set starting cash
        self.broker.set_starting_cash(self.initial_cash)
        
        # Initialize algorithm
        self.algorithm = self.algorithm_class()
        self.algorithm._broker = self.broker
        self.algorithm._symbols = available_symbols
        
        # Initialize algorithm
        self.algorithm.Initialize()
        
        # Get all timestamps
        all_timestamps = set()
        for symbol_data in data_cache.values():
            all_timestamps.update(symbol_data.index)

        '''
        data cache:
        dict like this: {'AAPL': <DataFrame of all AAPL data>, 'GOOG': <DataFrame of all GOOG data>}

        '''
        
        # Main event loop
        for timestamp in sorted(all_timestamps):
            slice_data = {}
            for symbol, symbol_data in data_cache.items():
                if timestamp in symbol_data.index:
                    slice_data[symbol] = symbol_data.loc[timestamp]
            
            if not slice_data:
                continue
            
            # Create TradeBar objects
            bars = {}
            for symbol, data in slice_data.items():
                bars[symbol] = TradeBar(
                    symbol=symbol,
                    open=float(data['open']),
                    high=float(data['high']),
                    low=float(data['low']),
                    close=float(data['close']),
                    volume=int(data['volume']),
                    end_time=timestamp
                )
            
            # Create Slice and call algorithm
            slice_obj = Slice(bars)
            self.algorithm._current_time = timestamp
            
            # Set current prices for percentage-based orders
            current_prices = {symbol: float(data['close']) for symbol, data in slice_data.items()}
            self.algorithm._current_prices = current_prices
            
            try:
                self.algorithm.OnData(slice_obj)
            except Exception as e:
                print(f"Error in algorithm at {timestamp}: {e}")
                continue
            
            # Settle orders
            for symbol in slice_data.keys():
                close_price = float(slice_data[symbol]['close'])
                self.broker.settle(symbol, close_price, timestamp)
            
            # Record equity curve
            snapshot = self.broker.snapshot()
            self.equity_curve.append({
                'time': timestamp,
                'equity': snapshot['total_equity'],
                'cash': snapshot['cash'],
                'holdings_value': snapshot['holdings_value'],
            })
        
        # Close all open positions at end of backtest (mark-to-market)
        final_holdings = self.broker.holdings()
        if final_holdings:
            final_timestamp = sorted(all_timestamps)[-1]
            for symbol, holding in final_holdings.items():
                if holding.quantity != 0:
                    # Get final price for this symbol
                    final_price = None
                    for symbol_data in data_cache.values():
                        if final_timestamp in symbol_data.index:
                            final_price = float(symbol_data.loc[final_timestamp]['close'])
                            break
                    
                    if final_price:
                        # Create closing order
                        closing_order = {
                            'type': 'market',
                            'symbol': symbol,
                            'quantity': abs(holding.quantity),
                            'is_buy': holding.quantity < 0,  # If short, buy to close; if long, sell to close
                            'submitted_at': final_timestamp,
                            'status': 'Submitted'
                        }
                        
                        # Execute closing order
                        self.broker.submit(closing_order)
                        self.broker.settle(symbol, final_price, final_timestamp)
        
        # Generate results
        fills = self.broker.get_fills()
        final_snapshot = self.broker.snapshot()
        performance_report = self.performance_metrics.generate_performance_report(
            equity_curve=self.equity_curve,
            fills=fills,
            initial_cash=self.initial_cash
        )
        
        return {
            'equity_curve': self.equity_curve,
            'fills': fills,
            'performance_report': performance_report,
            'final_snapshot': final_snapshot,
            'start_date': start_date,
            'end_date': end_date,
            'symbols': symbols,
            'initial_cash': self.initial_cash,
        }


