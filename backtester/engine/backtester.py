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
                 commission_rate=0.005,
                 slippage_bps=10,
                 max_volume_pct=0.1,
                 allow_shorting=True):
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
        self.slippage_bps = slippage_bps
        self.max_volume_pct = max_volume_pct
        self.allow_shorting = allow_shorting

    def run_backtest(self, 
                    start_date,
                    end_date,
                    symbols):
        if self.algorithm_class is None:
            raise ValueError("algorithm_class must be provided to Backtester")
        
        data_cache = self.data_manager.get_universe_data(symbols, start_date, end_date, auto_download=True)
        
        if not data_cache:
            raise ValueError("No data available for any symbols")
        
        available_symbols = list(data_cache.keys())
        if len(available_symbols) < len(symbols):
            missing = set(symbols) - set(available_symbols)
            print(f"Warning: Could not get data for: {missing}")
        
        self.broker.set_starting_cash(self.initial_cash)
        self.algorithm = self.algorithm_class()
        
        # Build a canonical trading calendar: intersection of all symbols' timestamps
        symbol_indices = [set(df.index) for df in data_cache.values()]
        if symbol_indices:
            common_index = set.intersection(*symbol_indices)
        else:
            common_index = set()

        # Fallback to union if intersection empty
        if not common_index:
            all_timestamps = set()
            for symbol_data in data_cache.values():
                all_timestamps.update(symbol_data.index)
        else:
            all_timestamps = common_index

        pending_targets = None  # dict of desired target shares to apply next bar

        for timestamp in sorted(all_timestamps):
            slice_data = {}
            for symbol, symbol_data in data_cache.items():
                if timestamp in symbol_data.index:
                    slice_data[symbol] = symbol_data.loc[timestamp]
            
            if not slice_data:
                continue
            
            bars = {}
            current_prices_open = {}
            current_prices_close = {}
            current_volumes = {}
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
                current_prices_open[symbol] = float(data['open'])
                current_prices_close[symbol] = float(data['close'])
                current_volumes[symbol] = int(data['volume'])
            
            slice_obj = Slice(bars)
            portfolio_view = self._create_portfolio_view()
            
            # Execute pending targets at this bar's open with slippage and liquidity constraints
            if pending_targets:
                self._execute_rebalance_at_open(
                    pending_targets,
                    current_prices_open,
                    current_volumes,
                    timestamp
                )
                pending_targets = None

            try:
                target_weights = self.algorithm.on_data(slice_obj, portfolio_view)
                if target_weights:
                    # Schedule rebalance for next bar using computed target shares
                    pending_targets = self._compute_target_shares(
                        target_weights,
                        current_prices_close
                    )
            except Exception as e:
                print(f"Error in algorithm at {timestamp}: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Update valuations at close for all symbols present
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
    
    def _compute_target_shares(self, target_weights, current_prices_close):
        if not target_weights:
            return None
        snapshot = self.broker.snapshot()
        total_value = snapshot['total_equity']
        target_shares = {}
        for symbol, weight in target_weights.items():
            if symbol not in current_prices_close:
                print(f"Warning: No price data for {symbol}, skipping")
                continue
            price = float(current_prices_close[symbol])
            desired_value = total_value * float(weight)
            shares = int(desired_value / price) if price > 0 else 0
            target_shares[symbol] = shares
        return target_shares if target_shares else None

    def _execute_rebalance_at_open(self, target_shares, prices_open, volumes, when):
        holdings = self.broker.holdings()
        snapshot = self.broker.snapshot()
        cash = float(snapshot['cash'])
        for symbol, desired_shares in target_shares.items():
            if symbol not in prices_open:
                print(f"Warning: No open price for {symbol} at {when}, skipping")
                continue
            open_price = float(prices_open[symbol])
            volume = int(volumes.get(symbol, 0))
            current_shares = holdings[symbol].quantity if symbol in holdings else 0
            diff = desired_shares - current_shares
            if diff == 0:
                continue
            is_buy = diff > 0
            # Slippage model
            slip = (self.slippage_bps or 0) / 10000.0
            exec_price = open_price * (1 + slip if is_buy else 1 - slip)

            # Liquidity cap
            liq_cap = int(volume * float(self.max_volume_pct)) if volume > 0 else abs(diff)
            qty = min(abs(diff), liq_cap) if liq_cap > 0 else 0

            if qty <= 0:
                continue

            # Cash constraints for buys; simple iterative adjustment to avoid negative cash
            if is_buy:
                # Try to find max affordable quantity under commission
                max_affordable = qty
                while max_affordable > 0:
                    commission = self.broker.calculate_commission(symbol, max_affordable, exec_price)
                    total_cost = max_affordable * exec_price + commission
                    if total_cost <= cash:
                        break
                    max_affordable -= 1
                qty = max_affordable
                if qty <= 0:
                    continue
                cash -= qty * exec_price + self.broker.calculate_commission(symbol, qty, exec_price)
            else:
                # Shorting allowed? If not, cap by current holdings
                if not self.allow_shorting:
                    qty = min(qty, current_shares)
                    if qty <= 0:
                        continue

            order = {
                'type': 'market',
                'symbol': symbol,
                'quantity': int(qty),
                'is_buy': is_buy,
            }
            self.broker.submit(order)
            # Fill at open with slippage-adjusted price
            self.broker.settle(symbol, exec_price, when)


