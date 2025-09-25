# HQG Backtester

V1 Plan...

Backtester inspired by LEAN.

---

## Interface for Researchers (Target UX)

```python
# strategy.py
from hqg_backtester import Algorithm

class MyStrategy(Algorithm):
    def Initialize(self):
        self.set_universe(["AAPL", "MSFT"])
        self.set_timeframe("2023-01-01", "2023-12-31")
        self.set_resolution("Daily")
        self.add_indicator("AAPL", "MACD", "MACD_9" fast=12, slow=26, signal=9)

    def OnData(self, data):
        if data["AAPL"]["MACD_9"] > 0:
            self.buy("AAPL", 100)
        else:
            self.liquidate()

if __name__ == "__main__":
    MyStrategy.backtest()
```

**Requirements:**

* Interactive Brokers Gateway running locally
* `.env` file with IBKR API credentials
* Python 3.7+

**Outputs:** Results will be saved in a timestamped directory containing:

* Performance metrics (equity curve, positions, trades)
* Data visualizations
* Execution metadata

---

## Principles

* **No Lookahead Bias:** Orders placed in `OnData` fill at next bar's open price
* **Market Orders Only:** Simple `buy`, `sell`, and `liquidate` operations
* **Transaction Costs:** Simplified configurable flat fee per trade
* **Portfolio Tracking:** Cash, positions, and equity tracked each bar
* **Data Provider Interface:** Modular design starting with CSV and IBKR support
* **Indicator Warmup:** Trading begins only after indicators have sufficient history

---

## Project Structure

```text
hqg-backtester/
    algorithm.py        # Base Algorithm class for strategy implementation
    engine/
        backtest.py     # Main backtesting engine
        broker.py       # Order execution and fee simulation
        portfolio.py    # Position and P&L tracking
        reporter.py     # Performance reporting and visualization
        clock.py        # Time management and bar iteration
        metrics.py      # Performance metrics calculation
    data/
        schema.py       # Market data schemas and validation
        indicators.py   # Technical indicator implementations
        providers/
            base.py     # Abstract data provider interface
            csv.py      # CSV data source implementation
            ibkr.py     # Interactive Brokers integration
    config/
        loader.py       # Configuration management
    tests/
        fixtures/       # Test data files
        live/          # Live trading system tests
        smoke/         # End-to-end integration tests
        unit/          # Unit test suite
```

---

## Execution Flow

1. **Configuration**
   * Load IBKR credentials from `.env`
   * Initialize algorithm instance
   * Set universe, timeframe, and indicators

2. **Data Preparation**
   * Fetch historical data through provider interface
   * Calculate technical indicators
   * Ensure sufficient warmup period

3. **Backtest Execution**
   * For each trading day:
      * Update portfolio state
      * Execute `OnData` with current bar data
      * Process orders at next bar's open price
      * Apply transaction costs
      * Log positions and performance

4. **Results Generation**
   * Calculate performance metrics
   * Generate trade log and statistics
   * Create visualization plots
   * Export execution metadata

---

## Basic Config -- Users Override in Initialize

```yaml
# config/defaults.yaml
data:
  provider: "csv"                 # or "ibkr"
  resolution: "Daily"
engine:
  fill_rule: "NEXT_BAR_OPEN"
  commission_per_order: 0.02
report:
  output_dir: "./runs/{timestamp}"
security:
  usage_key_required: true
```

Environment (.env):
```
HQG_USAGE_KEY=abc123
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
```

> IBKR Gateway must be installed and running (shared account).

---

## Minimal public API (user code)

```python
# In Algorithm
self.set_universe(list[str])
self.set_timeframe(start:str, end:str)            # "YYYY-MM-DD"
self.set_resolution("Daily")                      # V1: Daily only
self.add_indicator(symbol, "SMA"/"EMA"/"MACD", **params)

# Trading actions (market orders, next-bar-open fill)
self.buy(symbol: str, qty: int)
self.sell(symbol: str, qty: int)
self.liquidate(symbol: str | None = None)
```

`OnData(data)` receives:
```python
data = {
  "AAPL": {
    "open": float, "high": float, "low": float, "close": float, "volume": float,
    "SMA20": float, "EMA50": float, "MACD": float, ...
          },
  "MSFT": {...},
    ...
        }
```

---

## Output Files

Each backtest run generates a timestamped directory containing:

* `equity.csv` - Portfolio value history
* `trades.csv` - Detailed trade execution log
* `positions.csv` - Daily position snapshots
* `equity.png` - Performance visualization
* `metadata.json` - Run configuration and execution details

## V1 Success Criteria

* Reproducible results (deterministic execution)
* No look-ahead bias in order execution
* Complete trade and performance logging
* Comprehensive test coverage
