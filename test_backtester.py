from datetime import datetime
from typing import Dict, List
from hqg import run, Algorithm

"""
═══════════════════════════════════════════════════════════════════════════════
📚 COMPLETE API GUIDE FOR NEW USERS
═══════════════════════════════════════════════════════════════════════════════

🚀 QUICK START:
---------------
1. Inherit from Algorithm
2. Implement Initialize() - set cash, parameters
3. Implement OnData(data) - your trading logic
4. Use place_order() to buy/sell

📝 MINIMAL EXAMPLE:
------------------
class MyStrategy(Algorithm):
    def Initialize(self):
        self.SetCash(100_000)  # $100k starting capital
        
    def OnData(self, data):
        for symbol, bar in data.Bars.items():
            if bar.close > bar.open:  # Price went up today
                self.place_order(symbol, 100, is_buy=True)

═══════════════════════════════════════════════════════════════════════════════
🔧 CORE METHODS YOU MUST IMPLEMENT:
═══════════════════════════════════════════════════════════════════════════════

def Initialize(self):
    '''Called once at start. Set your cash, parameters, etc.'''
    self.SetCash(100_000)           # Set starting capital
    self.my_param = 20              # Custom parameters
    
def OnData(self, data):
    '''Called every trading day with market data'''
    # Access data for all symbols:
    for symbol, bar in data.Bars.items():
        print(f"{symbol}: ${bar.close}")
        
    # Or access specific symbol:
    if 'AAPL' in data.Bars:
        aapl = data.Bars['AAPL']
        print(f"AAPL: O=${aapl.open} H=${aapl.high} L=${aapl.low} C=${aapl.close}")

═══════════════════════════════════════════════════════════════════════════════
💰 TRADING METHODS:
═══════════════════════════════════════════════════════════════════════════════

# Buy/Sell stocks:
self.place_order("AAPL", 100, is_buy=True)   # Buy 100 shares of AAPL
self.place_order("AAPL", 50, is_buy=False)   # Sell 50 shares of AAPL

# Limit orders:
self.place_order("AAPL", 100, is_buy=True, 
                    order_type="limit", limit_price=150.0)

═══════════════════════════════════════════════════════════════════════════════
📊 DATA ACCESS:
═══════════════════════════════════════════════════════════════════════════════

# In OnData(self, data):

# Get all symbols with data today:
symbols = list(data.Bars.keys())

# Loop through all symbols:
for symbol, bar in data.Bars.items():
    price = bar.close
    volume = bar.volume
    
# Access specific symbol:
if 'AAPL' in data.Bars:
    aapl_bar = data.Bars['AAPL']
    
# TradeBar properties:
bar.symbol      # "AAPL"
bar.open        # Opening price
bar.high        # High price  
bar.low         # Low price
bar.close       # Closing price
bar.volume      # Volume traded
bar.end_time    # Timestamp of this bar

═══════════════════════════════════════════════════════════════════════════════
💼 PORTFOLIO ACCESS:
═══════════════════════════════════════════════════════════════════════════════

# Get current portfolio info:
snapshot = self._broker.snapshot()

cash = snapshot['cash']                    # Available cash
total_equity = snapshot['total_equity']    # Total portfolio value
holdings = snapshot['holdings']            # Dict of current positions

# Check specific position:
current_holdings = self._broker.holdings()
if 'AAPL' in current_holdings:
    aapl_position = current_holdings['AAPL']
    shares = aapl_position.quantity
    avg_price = aapl_position.average_price

═══════════════════════════════════════════════════════════════════════════════
🛠️ UTILITY METHODS:
═══════════════════════════════════════════════════════════════════════════════

# Logging (appears in backtest output):
self.log("Bought AAPL at $150")
self.log(f"Portfolio value: ${total_equity:,.2f}")

# Set initial cash:
self.SetCash(100_000)  # $100,000

═══════════════════════════════════════════════════════════════════════════════
📈 COMMON STRATEGY PATTERNS:
═══════════════════════════════════════════════════════════════════════════════

# 1. BUY AND HOLD:
def OnData(self, data):
    if not hasattr(self, 'bought'):
        for symbol in data.Bars.keys():
            self.place_order(symbol, 100, is_buy=True)
        self.bought = True

# 2. MOMENTUM (buy winners):
def Initialize(self):
    self.SetCash(100_000)
    self.price_history = {}
    
def OnData(self, data):
    # Store price history
    for symbol, bar in data.Bars.items():
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(bar.close)
        
    # Buy if price increased over last 5 days
    for symbol, prices in self.price_history.items():
        if len(prices) >= 5:
            if prices[-1] > prices[-5]:  # Price up over 5 days
                self.place_order(symbol, 50, is_buy=True)

# 3. MEAN REVERSION (buy losers):
def OnData(self, data):
    for symbol, bar in data.Bars.items():
        if bar.close < bar.open * 0.95:  # Down 5% today
            self.place_order(symbol, 100, is_buy=True)

# 4. REBALANCING:
def Initialize(self):
    self.SetCash(100_000)
    self.rebalance_days = 0
    
def OnData(self, data):
    self.rebalance_days += 1
    if self.rebalance_days >= 30:  # Rebalance monthly
        self.rebalance_days = 0
        self.rebalance_portfolio(data)
        
def rebalance_portfolio(self, data):
    # Sell all positions
    holdings = self._broker.holdings()
    for symbol, position in holdings.items():
        if position.quantity > 0:
            self.place_order(symbol, position.quantity, is_buy=False)
            
    # Buy equal weights
    portfolio_value = self._broker.snapshot()['total_equity']
    symbols = list(data.Bars.keys())
    weight_per_symbol = portfolio_value / len(symbols)
    
    for symbol, bar in data.Bars.items():
        shares = int(weight_per_symbol / bar.close)
        if shares > 0:
            self.place_order(symbol, shares, is_buy=True)

═══════════════════════════════════════════════════════════════════════════════
⚠️  IMPORTANT NOTES:
═══════════════════════════════════════════════════════════════════════════════

• OnData() is called once per trading day for each symbol
• Orders are executed at the close price of the current bar
• Commission is automatically calculated and deducted
• All positions are automatically closed at the end of backtest
• Use self.log() to debug your strategy
• Access current time with self._current_time

═══════════════════════════════════════════════════════════════════════════════
🎯 RUNNING YOUR STRATEGY:
═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime
from hqg.engine.backtester import Backtester

# Your strategy class here...

# Run backtest:
backtester = Backtester(
    algorithm_class=MyStrategy,
    initial_cash=100_000,
    commission_rate=0.005  # $0.005 per share
)

results = backtester.run_backtest(
    start_date=datetime(2022, 1, 1),
    end_date=datetime(2023, 12, 31),
    symbols=['AAPL', 'GOOGL', 'MSFT']  # Data auto-downloaded
)

═══════════════════════════════════════════════════════════════════════════════
"""

class MyStrategy(Algorithm):
    def Initialize(self):
        self.target_allocations: Dict[str, float] = {
            "SPY": 0.40,
            "AAPL": 0.15,
            "MSFT": 0.15,
            "GOOGL": 0.15,
            "VTI": 0.15,
        }
        self.rebalance_every_days: int | None = None

        self._allocated = False
        self._last_rebalance = None



    def OnData(self, data):
        # Wait until we have at least one price for each symbol we want to trade
        prices = {}
        for symbol in list(self.target_allocations.keys()):
            bar = data.get(symbol)
            if bar is None:
                return
            prices[symbol] = float(bar.close)

        # Decide whether to allocate/rebalance
        do_allocate = False
        if not self._allocated:
            do_allocate = True
        elif self.rebalance_every_days:
            if self._last_rebalance is None:
                do_allocate = True
            else:
                if (data.time - self._last_rebalance).days >= self.rebalance_every_days:
                    do_allocate = True

        if not do_allocate:
            return

        # Get portfolio snapshot
        snapshot = self._broker.snapshot()
        total_equity = snapshot["total_equity"]  # cash + holdings_value
        # Note: for initial allocation this should equal starting cash

        # Current holdings (may be empty)
        current_holdings = self._broker.holdings()  # symbol -> Holding object

        # Compute desired shares for each symbol (floor to whole shares)
        desired_shares = {}
        for symbol, weight in self.target_allocations.items():
            target_value = weight * total_equity
            price = prices[symbol]
            shares = int(target_value // price)  # floor to whole shares
            desired_shares[symbol] = max(0, shares)

        # Compute deltas (sell first to free cash)
        sells = {}
        buys = {}
        for symbol, target_qty in desired_shares.items():
            current_qty = current_holdings.get(symbol).quantity if symbol in current_holdings else 0
            delta = target_qty - current_qty
            if delta < 0:
                sells[symbol] = abs(delta)
            elif delta > 0:
                buys[symbol] = delta

        # Submit sells first
        for symbol, qty in sells.items():
            if qty > 0:
                # sell to reduce holdings
                self.place_order(symbol, qty, is_buy=False, order_type="market")

        # Then submit buys (broker will charge commission and reduce cash)
        for symbol, qty in buys.items():
            if qty > 0:
                self.place_order(symbol, qty, is_buy=True, order_type="market")

        # Mark allocation done
        self._allocated = True
        self._last_rebalance = data.time

run(
    algorithm_class=MyStrategy,
    universe=["AAPL", "MSFT", "GOOGL", "SPY", "VTI"],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)