from typing import Dict, List
from datetime import datetime
from uuid import uuid4
from .response import OrderType, Trade
from hqg_algorithms import Slice

class Portfolio:
    """
    Manages portfolio state including cash and holdings.
    Executes rebalances and tracks all trades.
    """
    
    def __init__(self, initial_cash: float, symbols: List[str]):
        self.cash = initial_cash
        self.positions: Dict[str, float] = {symbol: 0.0 for symbol in symbols}  # ticker: quantity owned
        self.equity_curve: Dict[datetime, float] = {}  # track NAV over time

    def update_equity_curve(self, timestamp: datetime, total_value: float) -> None:
        self.equity_curve[timestamp] = total_value
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """ (cash + positions) """
        positions_value = sum(
            self.positions.get(symbol, 0) * prices.get(symbol, 0)
            for symbol in self.positions
        )
        return self.cash + positions_value

    def get_weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        """ returns dict of ticker: weight. Sum will be <= 1, as we will not return Cash """
        wts = {}
        tv = self.get_total_value(prices)
        for tick, quantity in self.positions.items():
            if tick not in prices:
                continue
            wt = prices[tick] * quantity / tv
            wts[tick] = wt
        return wts

    
    def rebalance(self, target_weights: Dict[str, float], prices: Dict[str, float], timestamp: datetime) -> List[Trade]:
        """
        Rebalance portfolio to target weights.
        
        Args:
            target_weights: Target allocation {symbol: weight}
            prices: Current prices for execution
            timestamp: Execution timestamp
            
        Returns:
            List of trades executed
        """
        trades = []
        
        # validate weights sum to <= 1.0
        total_weight = sum(target_weights.values())
        if total_weight > 1.0001:
            raise ValueError(f"Target weights sum to {total_weight}, must be <= 1.0")
        
        # current portfolio value
        total_value = self.get_total_value(prices)
        
        # target positions (in shares)
        target_positions = {}
        for symbol, weight in target_weights.items():
            if symbol not in prices:
                raise ValueError(f"No price available for {symbol}")
            
            target_value = total_value * weight
            target_shares = target_value / prices[symbol]
            target_positions[symbol] = target_shares
        
        # execute trades for each symbol
        for symbol in self.positions:
            current_shares = self.positions[symbol]
            target_shares = target_positions.get(symbol, 0.0)
            
            shares_to_trade = target_shares - current_shares
            
            # skip if change is negligible (under $1)
            if abs(shares_to_trade * prices[symbol]) < 1:
                continue
            
            if symbol not in prices:
                continue
            
            price = prices[symbol]
            trade_value = abs(shares_to_trade) * price
            
            # execute buy or sell 
            # (assume x1 margin, so cash can be momentarily negative as we rebalance)
            if shares_to_trade > 0:
                self.positions[symbol] += shares_to_trade
                self.cash -= trade_value
                
                trades.append(Trade(
                    id=str(uuid4()),
                    timestamp=timestamp,
                    symbol=symbol,
                    action=OrderType.BUY,
                    shares=shares_to_trade,
                    price=price,
                ))
            
            elif shares_to_trade < 0:
                # Sell
                shares_to_sell = abs(shares_to_trade)
                
                self.positions[symbol] -= shares_to_sell
                self.cash += trade_value
                    
                trades.append(Trade(
                    id=str(uuid4()),
                    timestamp=timestamp,
                    symbol=symbol,
                    action=OrderType.SELL,
                    shares=shares_to_sell,
                    price=price,
                ))
        
        return trades
    
    def update_ohlc(self, timestamp: datetime, slice_obj: Slice) -> Dict:
        """
        Calculate portfolio OHLC based on current positions and market OHLC.
        
        Args:
            timestamp: Current timestamp
            slice_obj: Slice object with market data
        
        Returns:
            Dict with timestamp and portfolio OHLC values
        """
        portfolio_open = self.cash
        portfolio_high = self.cash
        portfolio_low = self.cash
        portfolio_close = self.cash
        
        for symbol, shares in self.positions.items():
            if shares <= 0:
                continue
                
            open_price = slice_obj[symbol].get("open")
            high_price = slice_obj[symbol].get("high")
            low_price = slice_obj[symbol].get("low")
            close_price = slice_obj[symbol].get("close")
            
            if open_price is not None:
                portfolio_open += shares * open_price
            if high_price is not None:
                portfolio_high += shares * high_price
            if low_price is not None:
                portfolio_low += shares * low_price
            if close_price is not None:
                portfolio_close += shares * close_price
        
        return {
            'timestamp': timestamp,
            'open': portfolio_open,
            'high': portfolio_high,
            'low': portfolio_low,
            'close': portfolio_close
        }