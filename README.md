# HQG Backtester

Lightweight, researcher-first Python backtester focused on quick strategy iteration and reproducible experiments.

This README is a concise reference for how to run the project, where the pieces live, and the recommended workflow for Quant Researchers.

## What changed

- Initial cash is set in the strategy's `Initialize()` (use `self.SetCash(...)`).
- Benchmarks are specified in the strategy entrypoint via `run(MyStrategy, benchmark="SPY")`.
- Data is stored locally in a DuckDB database at `backtester/db/market_data.db` for fast querying and analysis.

## Quick start (recommended)

1. Create a virtualenv and install dev deps (macOS / zsh):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

2. Run the test example:

```bash
python test_percentage_orders.py
```

This demonstrates the percentage-based order API and backtesting functionality.

## Files & responsibilities (where to look)

- `test_percentage_orders.py` — Example strategy demonstrating the percentage-based order API.
- `backtester/engine/backtester.py` — Backtest loop, slice construction, portfolio updates, equity curve collection.
- `backtester/api/algorithm.py` — Algorithm base class and helper methods available to strategies.
- `backtester/data/sources/ibkr.py` — IBKR data source (primary).
- `backtester/data/sources/yfinance.py` — yfinance fallback data source.
- `backtester/analysis/metrics.py` — Performance metrics (returns, Sharpe, drawdown, alpha, beta, trade metrics).

## How a run works (quick)

1. `runner.run()` loads `config.yml` from the strategy folder and sets up logging.
2. DataManager asks LocalStorage for each symbol; if missing, it auto-pulls from IBKR then yfinance and stores Parquet files.
3. Backtester is instantiated with the strategy class; `Initialize()` is called once.
4. For each bar, Backtester builds a `Slice` and calls `OnData(slice)`.
5. Orders are submitted via `place_order()` → BrokerAdapter executes at close price (fills returned synchronously for backtests).
6. After loop, `PerformanceMetrics.generate_performance_report()` is called and printed; if a benchmark was passed, comparative metrics are included.

## Configuration

Minimal `config.yml` (next to `main.py` in strategy folder):

```yaml
owner: "you"
version: "1.0"
strategy_name: "my_strategy"
symbols:
  - "AAPL"
  - "GOOGL"
mode: "backtest"
start_date: "2023-01-01"
end_date: "2023-12-31"
```

Notes:
- Do not set `initial_cash` in config — set it in `Initialize()` with `self.SetCash(...)`.
- To compare against a benchmark, call `run(MyStrategy, benchmark="SPY")`.

## Tests

Run unit tests with pytest from the repo root:

```bash
pytest -q
```

If you add new features, add unit tests under `tests/` and run the suite before submitting a PR.

## Developer notes & TODOs

- Storage: Market data is stored in DuckDB at `backtester/db/market_data.db` and managed by `backtester/data/database.py`.
- Data sources: primary IBKR (requires credentials) with a yfinance fallback for convenience.
- Metrics: `analysis/metrics.py` includes Sharpe, Drawdown, alpha, beta, trade metrics and an informative summary that separates closed trades from open positions.
- API: Use the `Algorithm` base class in `backtester/api/algorithm.py` for implementing strategies.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This software is provided for educational and research purposes only. It is not intended for use in live trading or as financial advice. Use at your own risk.

## Contact

For questions or collaboration, contact the Husky Quantitative Group at [your contact email or GitHub link].