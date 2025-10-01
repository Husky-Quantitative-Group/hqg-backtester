"""
Simple Momentum Strategy
========================

This strategy demonstrates the basic API for creating backtesting strategies.

HQG Backtester API Documentation
=================================

1. ALGORITHM BASE CLASS
   - Your strategy must inherit from `Algorithm`
   - Implement two required methods: Initialize() and OnData(data)

2. INITIALIZATION (Initialize method)
   
   a) Set Initial Capital:
      self.SetCash(amount)
      Example: self.SetCash(100_000)  # $100,000 starting capital
   
   b) Define Universe (symbols are auto-loaded from config.yml):
      - Symbols specified in config.yml are automatically available
      - No need to call AddEquity() - this is handled automatically
      - Access available symbols via data.trade_bars.keys() in OnData
   
   c) Set Parameters:
      self.lookback_period = 20  # Custom strategy parameters
      self.threshold = 0.05
      
   d) Initialize Data Structures:
      self.history = {}  # Store historical data if needed
      self.indicators = {}  # Store indicator values

3. DATA HANDLING (OnData method)
   
   Called on each trading day with current market data.
   
   Parameters:
   - data: Slice object containing market data for all symbols
     
   Access Market Data:
   - data.trade_bars: dict[str, TradeBar]
     * Keys: symbol strings (e.g., "AAPL", "GOOGL")
     * Values: TradeBar objects with OHLCV data
     
   TradeBar Properties:
   - trade_bar.symbol: str - Symbol name
   - trade_bar.open: float - Opening price
   - trade_bar.high: float - High price
   - trade_bar.low: float - Low price
   - trade_bar.close: float - Closing price
   - trade_bar.volume: int - Trading volume
   - trade_bar.end_time: datetime - Bar timestamp
   
   Example:
   ```python
   def OnData(self, data):
       for symbol, bar in data.trade_bars.items():
           if bar.close > bar.open:
               # Price increased
               self.place_order(symbol, 10, is_buy=True)
   ```

4. ORDER PLACEMENT
   
   self.place_order(symbol, quantity, is_buy)
   
   Parameters:
   - symbol: str - Symbol to trade (e.g., "AAPL")
   - quantity: int - Number of shares (must be positive)
   - is_buy: bool - True for buy orders, False for sell orders
   
   Examples:
   ```python
   self.place_order("AAPL", 100, is_buy=True)   # Buy 100 shares of AAPL
   self.place_order("GOOGL", 50, is_buy=False)  # Sell 50 shares of GOOGL
   ```
   
   Notes:
   - Orders are executed immediately at current bar's close price
   - No need to check cash/position availability (broker validates)
   - Failed orders (insufficient funds/shares) are logged but don't crash

5. PORTFOLIO ACCESS
   
   self.portfolio: Portfolio object with current positions and cash
   
   Properties:
   - self.portfolio.cash: float - Current cash balance
   - self.portfolio.positions: dict[str, Position]
     * Keys: symbol strings
     * Values: Position objects
   
   Position Properties:
   - position.symbol: str
   - position.quantity: int - Current shares held (positive for long)
   - position.average_price: float - Average purchase price
   - position.market_value: float - Current market value (not yet implemented)
   
   Example:
   ```python
   def OnData(self, data):
       if "AAPL" in self.portfolio.positions:
           pos = self.portfolio.positions["AAPL"]
           if pos.quantity > 100:
               # Reduce position
               self.place_order("AAPL", 50, is_buy=False)
   ```

6. INDICATORS & CALCULATIONS
   
   You can implement custom indicators using pandas/numpy:
   
   Example - Simple Moving Average:
   ```python
   def Initialize(self):
       self.SetCash(100_000)
       self.history = {}
       self.sma_period = 20
   
   def OnData(self, data):
       for symbol, bar in data.trade_bars.items():
           # Store historical prices
           if symbol not in self.history:
               self.history[symbol] = []
           
           self.history[symbol].append(bar.close)
           
           # Keep only needed history
           if len(self.history[symbol]) > self.sma_period:
               self.history[symbol].pop(0)
           
           # Calculate SMA when enough data
           if len(self.history[symbol]) >= self.sma_period:
               sma = sum(self.history[symbol]) / self.sma_period
               
               # Trading logic
               if bar.close > sma:
                   self.place_order(symbol, 10, is_buy=True)
   ```

7. CONFIGURATION (config.yml)
   
   The following parameters are read from config.yml:
   - symbols: List[str] - Symbols to backtest
   - start_date: str - Backtest start (YYYY-MM-DD)
   - end_date: str - Backtest end (YYYY-MM-DD)
   - mode: str - "backtest" (live trading not yet supported)
   
   Example config.yml:
   ```yaml
   owner: "your_name"
   version: "1.0.0"
   strategy_name: "simple_momentum_strategy"
   symbols:
     - "AAPL"
     - "GOOGL"
     - "MSFT"
   mode: "backtest"
   start_date: "2023-01-01"
   end_date: "2024-01-01"
   ```

8. DATA INGESTION
   
   - Historical data is automatically fetched if not available locally
   - Primary source: Interactive Brokers (IBKR)
   - Fallback source: Yahoo Finance (yfinance)
   - Data is cached in data/daily/ directory as Parquet files
   - No manual data setup required

9. BENCHMARKING
   
   Compare your strategy against a benchmark (e.g., SPY for S&P 500):
   
   ```python
   if __name__ == "__main__":
       run(SimpleMomentumStrategy, benchmark="SPY")
   ```
   
   The benchmark return will be calculated and compared to your strategy.

10. PERFORMANCE METRICS
    
    After backtest completion, you'll receive:
    - Total Return (%)
    - Sharpe Ratio
    - Max Drawdown (%)
    - Trade Metrics (if trades were closed)
    - Open Positions (for buy-and-hold strategies)
    - Benchmark Comparison (if specified)

"""

from runner import run
from hqg_backtester.api import Algorithm


class SimpleMomentumStrategy(Algorithm):
    """
    A simple momentum strategy that buys when price closes above open.
    
    This demonstrates basic usage of the Algorithm API.
    """
    
    def Initialize(self):
        """
        Initialize the strategy.

        """
        # Set initial cash for the strategy
        self.SetCash(100_000)  # $100,000 starting capital

    def OnData(self, data):
        """
        Execute strategy logic on each trading day.

        """
        for symbol, trade_bar in data.trade_bars.items():
            if trade_bar.close > trade_bar.open:  # Momentum condition
                self.place_order(symbol, 10, is_buy=True)


if __name__ == "__main__":
    # Run the backtest with SPY as benchmark for comparison
    run(SimpleMomentumStrategy, benchmark="SPY")