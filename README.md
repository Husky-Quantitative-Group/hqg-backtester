# HQG Backtester Plan (V1)

Backtester inspired by LEAN.

---

## What the researcher does (UX)

```bash
pip install hqg-backtester
```

```python
# examples/my_algo.py
from hqg_backtester import Algorithm

class CustomAlgo(Algorithm):
    def initialize(self):
        self.set_universe(["AAPL", "MSFT"])
        self.set_timeframe("2021-01-01", "2021-12-31")
        self.set_resolution("Daily")
        self.add_indicator("AAPL", "MACD", fast=12, slow=26, signal=9) 
        # or self.MACD("AAPL", "MACD_9" fast=12, slow=26, signal=9)

    def OnData(self, data):
        # data["AAPL"].close, data["AAPL"].MACD_9, 
        # or data["AAPL"].Indicators["MACD"].value) -- can iterate & make less verbose
        if data["AAPL"].indicators["MACD"].value > 0:
            self.buy("AAPL", 10)
        else:
            self.sell("AAPL", 10)

if __name__ == "__main__":
    CustomAlgo().Backtest()
```

**Outputs:** `runs/<timestamp>/{equity.csv, trades.csv, positions.csv, equity.png, drawdown.png, run.json, etc.}`

Note that the Researchers will need:
*  .env file to have shared IBKR API key & hqg_backtester usage key (ie, abc123)
* IBKR Gateway running locally (or in server, later on)

---

## Essentials we enforce in V1

- **No lookahead:** Orders placed in `OnData` fill at **next bar open**.
- **Warmup:** `OnData` runs only after indicators have enough history.
- **Only market orders:** `buy`, `sell`, `liquidate` (all or per symbol).
- **Fees:** Flat per order (e.g., $0.02).
- **Portfolio:** Cash, positions, equity tracked each bar.
- **Data provider decoupled:** Start with CSV; IBKR fetch behind one interface.
- **Usage key & secrets:** Require `HQG_USAGE_KEY` and IBKR creds in `.env`.

---

## File structure

```
hqg-backtester/
  hqg_backtester/
    __init__.py
    algorithm.py        # Base Algorithm (user inherits); Algorithm.Backtest()
    engine/
      backtest.py       # Orchestrates init → loop → report
      broker.py         # Order queue, next-bar-open fills, fees
      portfolio.py      # Cash/positions/equity/PnL
      reporter.py       # Write CSVs + simple matplotlib plots
      clock.py          # Bar iterator, warmup gating
    data/
      schema.py         # Bar model: timestamp,symbol,open,high,low,close,volume
      provider_base.py  # get_bars(symbols, start, end, resolution)
      provider_csv.py   # CSV provider (default)
      provider_ibkr.py  # IBKR provider (fetch → CSV)
      indicators.py     # SMA, EMA, MACD (minimal)
    security/
      license_check.py  # Validate HQG_USAGE_KEY
      secrets.py        # Load .env (IBKR + others)
    config/
      defaults.yaml     # env overrides allowed
  examples/
  tests/
  pyproject.toml
  README.md
```

---

## How it runs (engine flow)

1) **Gate:** `license_check` verifies `HQG_USAGE_KEY`.  
2) **Secrets:** load `.env` (IBKR creds).  
3) **Init:** algorithm `initialize()` → symbols, dates, indicators.  
4) **Data:** provider builds a **master CSV** per symbol (canonical schema).  
5) **Warmup:** indicators are calculated & added to CSVs; no `OnData` until ready.  
6) **Loop:** for each bar  
   - Snapshot prior state → `OnData(data_snapshot)`  
   - Queue orders → **fill next bar open**  
   - Apply fees → update portfolio → log  
7) **Report:** write CSVs, basic plots, and a `run.json` manifest.

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
    "bar": Bar(ts, open, high, low, close, volume),
    "indicators": {"MACD": Indicator(value=..., ready=True), ...}
  },
  ...
}
```

---

## Outputs (V1)

- `equity.csv` – timestamp, equity  
- `trades.csv` – ts, symbol, side, qty, fill_price, fee, cash_after, equity_after  
- `positions.csv` – ts, symbol, qty, avg_price  
- `equity.png` – equity curve  
- `drawdown.png` – drawdown curve  
- `run.json` – symbols, dates, provider, commit hash (if available), config hash
- Etc.

---

## Quick start (dev)

```bash
# clone repo, then:
pip install -e .
python examples/example_algo_macd.py
```

---

## V1 success criteria

- Deterministic outputs on repeated runs (same inputs → same CSV hashes).  
- No lookahead leakage (orders filled only on next bar open).  
- Produces the 3 CSVs + 2 PNGs + run.json.  
