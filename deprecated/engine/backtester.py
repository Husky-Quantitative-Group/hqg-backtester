from datetime import datetime
from pathlib import Path

from hqg_algorithms import Strategy

from ..analysis.metrics import PerformanceMetrics
from ..data.manager import DataManager
from ..execution.broker import IBBroker
from ..data_types import Slice, TradeBar

import pandas as pd


class Backtester:
    def __init__(self, 
                 data_path=None,
                 algorithm_class=None,
                 initial_cash=100000.0,
                 commission_rate=0.005):
        if data_path is None:
            # Default to root-level data/ directory
            data_path = Path(__file__).parent.parent.parent / "data"
        self.data_path = Path(data_path)
        self.algorithm_class = algorithm_class
        self.initial_cash = initial_cash
        
        self.data_manager = DataManager(str(self.data_path))
        self.broker = IBBroker(commission_rate=commission_rate)
        self.performance_metrics = PerformanceMetrics()
        
        self.algorithm = None
        self.equity_curve = []

    def run_backtest(self, 
                    start_date,
                    end_date,
                    symbols):
        
        data_cache = self.data_manager.get_universe_data(symbols, start_date, end_date, auto_download=True)
        
        if not data_cache:
            raise ValueError("No data available for any symbols")
        
        available_symbols = list(data_cache.keys())
        if len(available_symbols) < len(symbols):
            missing = set(symbols) - set(available_symbols)
            print(f"Warning: Could not get data for: {missing}")
        
        self.broker.set_starting_cash(self.initial_cash)
        self.algorithm = self.algorithm_class()
        
        all_timestamps = set()
        for symbol_data in data_cache.values():
            all_timestamps.update(symbol_data.index)
        
        for timestamp in sorted(all_timestamps):
            slice_data = {}
            for symbol, symbol_data in data_cache.items():
                if timestamp in symbol_data.index:
                    slice_data[symbol] = symbol_data.loc[timestamp]
            
            if not slice_data:
                continue
            
            bars = {}
            current_prices = {}
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
                current_prices[symbol] = float(data['close'])
            
            slice_obj = Slice(bars)
            portfolio_view = self._create_portfolio_view()
            
            try:
                target_weights = self.algorithm.on_data(slice_obj, portfolio_view)
                if target_weights:
                    self._rebalance_to_targets(target_weights, current_prices)
            except Exception as e:
                print(f"Error in algorithm at {timestamp}: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            for symbol in slice_data.keys():
                close_price = float(slice_data[symbol]['close'])
                self.broker.settle(symbol, close_price, timestamp)
            
            snapshot = self.broker.snapshot()
            self.equity_curve.append({
                'time': timestamp,
                'equity': snapshot['total_equity'],
                'cash': snapshot['cash'],
                'holdings_value': snapshot['holdings_value'],
            })
        
        final_holdings = self.broker.holdings()
        if final_holdings:
            final_timestamp = sorted(all_timestamps)[-1]
            for symbol, holding in final_holdings.items():
                if holding.quantity != 0:
                    final_price = None
                    if symbol in data_cache and final_timestamp in data_cache[symbol].index:
                        final_price = float(data_cache[symbol].loc[final_timestamp]['close'])
                    
                    if final_price:
                        closing_order = {
                            'type': 'market',
                            'symbol': symbol,
                            'quantity': abs(holding.quantity),
                            'is_buy': holding.quantity < 0,
                            'submitted_at': final_timestamp,
                            'status': 'Submitted'
                        }
                        self.broker.submit(closing_order)
                        self.broker.settle(symbol, final_price, final_timestamp)
        
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
    
    def _create_portfolio_view(self):
        snapshot = self.broker.snapshot()
        holdings = self.broker.holdings()
        
        class SimplePortfolioView:
            def __init__(self, cash, total_equity, holdings):
                self.cash = cash
                self.total_equity = total_equity
                self._holdings = holdings
            
            def holdings(self):
                return {sym: {'quantity': h.quantity, 'avg_price': h.average_price} 
                        for sym, h in self._holdings.items()}
        
        return SimplePortfolioView(snapshot['cash'], snapshot['total_equity'], holdings)
    
    def _rebalance_to_targets(self, target_weights, current_prices):
        if not target_weights:
            return
        
        snapshot = self.broker.snapshot()
        total_value = snapshot['total_equity']
        
        for symbol, weight in target_weights.items():
            if symbol not in current_prices:
                print(f"Warning: No price data for {symbol}, skipping")
                continue
            
            target_value = total_value * weight
            current_price = current_prices[symbol]
            target_shares = int(target_value / current_price)
            
            if target_shares <= 0:
                continue
            
            holdings = self.broker.holdings()
            current_shares = holdings[symbol].quantity if symbol in holdings else 0
            shares_diff = target_shares - current_shares
            
            if shares_diff == 0:
                continue
            
            order = {
                'type': 'market',
                'symbol': symbol,
                'quantity': abs(shares_diff),
                'is_buy': shares_diff > 0,
            }
            self.broker.submit(order)


