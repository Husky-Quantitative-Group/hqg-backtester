# HQG Backtester API

FastAPI service for running user-submitted `hqg_algorithms` strategies against historical market data, with a validation pipeline and sandboxed Docker execution.

## What This Repo Actually Does

The primary supported path is the HTTP API:

1. Accepts strategy code + backtest parameters
2. Performs AST-based static analysis (imports, builtins, attributes, syntax)
3. Loads the strategy to extract `universe()` and `cadence()`
4. Fetches market data (Yahoo Finance) with a parquet cache
5. Executes the strategy inside a locked-down Docker sandbox container
6. Validates execution output
7. Computes performance metrics and returns a frontend-shaped response

## For Researchers: the `hqg` CLI

Researchers do not run this repo. They install a small client package that talks
to the hosted service over HTTP, and never see Docker, JSON or the API.

```bash
pip install hqg-backtester     # pulls only httpx + hqg-algorithms
hqg health                     # confirm the service is reachable
```

Write a strategy as an ordinary Python file:

```python
# strategy.py
from hqg_algorithms import Strategy, Cadence, BarSize, Slice, PortfolioView, Signal, TargetWeights, Hold

class MyStrategy(Strategy):
    universe = ["SPY", "TLT"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def __init__(self):
        self.isInvested = False

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        if not self.isInvested:
            self.isInvested = True
            return TargetWeights({"SPY": 0.6, "TLT": 0.4})
        return Hold()
```

Run it:

```bash
hqg run strategy.py --start 2023-01-01 --end 2024-01-01 --capital 100000
```

```
  job 87f54c17-4513-4da8-9449-be5a12bd7a75
  running
  completed

  strategy.py · 2023-01-01 → 2024-01-01 · $100,000 · 4.1s

  Return                           Risk
    Total                 +16.4%   Max drawdown          -12.3%
    Annualized            +16.6%   Ann. volatility        11.2%
    Net profit          +$16,363   VaR 95%                -1.1%
    Final equity        $116,363   CVaR 95%               -1.4%
                                   Drawdown (bars)          102

  Ratios                           Market
    Sharpe                  0.97   Alpha                  -2.1%
    Sortino                 1.44   Beta                    0.68
    Calmar                  1.35   Orders                     2
    PSR                     0.32   Volume              $100,000
```

### Commands

| Command | Purpose |
| --- | --- |
| `hqg run STRATEGY --start D --end D` | run a backtest and wait for the result |
| `hqg run ... --json` | raw result JSON on stdout, summary on stderr |
| `hqg run ... --no-wait` | submit and exit, printing the job id |
| `hqg run ... --verbose` | also print the strategy's `self.log()` output |
| `hqg status JOB_ID` | fetch a run submitted earlier |
| `hqg cancel JOB_ID` | cancel a job that is still `PENDING` |
| `hqg health` | check that the service is reachable |

`--start` and `--end` are required and must be `YYYY-MM-DD`. `--capital`
defaults to 10000. Ctrl-C during a run cancels the job rather than orphaning it.

Exit codes: `0` success, `1` the run or service failed, `2` bad input
(unparseable dates, missing file, invalid strategy), `130` interrupted.

### Gotchas

- **Do not call `print()` in a strategy.** The sandbox writes its result to
  stdout, so a stray `print()` corrupts it and the job fails with a JSON parse
  error. Use `self.log()`, which surfaces under `hqg run --verbose`.
- Strategies receive only the current bar. Keep your own rolling window on
  `self` (see the `SimpleSMA` example below) — there is no history API.
- Job state is in memory. If the service restarts, `hqg status` returns
  "no longer exists".

### Client configuration

`hqg` needs no config file. These environment variables override the defaults,
and exist mainly for pointing the client at a local service:

| Variable | Default | Meaning |
| --- | --- | --- |
| `HQG_API_URL` | the hosted VM | base URL of the backtesting service |
| `HQG_REQUEST_TIMEOUT` | `30` | seconds per HTTP call |
| `HQG_POLL_INTERVAL` | `5` | seconds between status polls |
| `HQG_MAX_RETRY_AFTER` | `60` | cap on a `Retry-After` the service asks for |

```bash
HQG_API_URL=http://localhost:8005 hqg run strategy.py --start 2023-01-01 --end 2024-01-01
```

Polls share the service's per-IP rate limit (60/min), which is why the client
backs off to `HQG_POLL_INTERVAL` rather than polling every second.

## Current API Surface

- `GET /health`
- `POST /api/v1/backtest`

Docker Compose exposes the API on `http://localhost:8005`.

## Quick Start (Docker Compose)

Prereqs:

- Docker Desktop / Docker Engine running
- Access to `/var/run/docker.sock` (the API container launches sandbox containers)

Run:

```bash
docker compose up --build
```

Always pass `--build` after pulling. `docker compose up -d` on its own reuses
the existing image, so the container silently runs stale code while your working
tree looks current.

This builds:

- `hqg-backtester-sandbox` (strategy execution image)
- `backtester-api` (FastAPI service)

API docs:

- Swagger UI: `http://localhost:8005/docs`
- ReDoc: `http://localhost:8005/redoc`

## Manual Local Setup (Without Compose)

Prereqs:
- Python 3.11 recommended (matches Docker images)
- Docker daemon running

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Build the sandbox image:

```bash
docker build -f Dockerfile.sandbox -t hqg-backtester-sandbox .
```

3. Start the API:

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

Manual run default URL: `http://localhost:8000`

## Request Format (`POST /api/v1/backtest`)

Required fields:

- `strategy_code` (string)
- `start_date` (ISO datetime)
- `end_date` (ISO datetime, must be after `start_date`)

Optional fields:

- `name` (string)
- `initial_capital` (float, default `10000`)
- `commission` (accepted by schema, currently not applied in v1)
- `slippage` (accepted by schema, currently not applied in v1)

### Example Request

```json
{
  "name": "Buy and Hold SPY/TLT",
  "strategy_code": """
from hqg_algorithms import (
    Strategy, Cadence, Slice, PortfolioView,
    BarSize, ExecutionTiming, Signal, TargetWeights, Hold,
)
from collections import deque

class SimpleSMA(Strategy):
    '''Go risk-on when SPY is above its 21-day mean, otherwise hold bonds.'''

    def __init__(self):
        self._window = 21
        self._q: deque[float] = deque(maxlen=self._window)

    def universe(self) -> list[str]:
        return ['SPY', 'BND']

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY, execution=ExecutionTiming.CLOSE_TO_NEXT_OPEN)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        spy_close = data.close('SPY')
        if spy_close is None:
            return Hold()

        self._q.append(spy_close)

        if len(self._q) < self._window:
            return TargetWeights({'BND': 1.0})  # hold bonds while warming up

        sma = sum(self._q) / len(self._q)

        if spy_close > sma:
            return TargetWeights({'SPY': 0.5, 'BND': 0.5})  # uptrend
        return TargetWeights({'BND': 1.0})                   # downtrend
""",
  "start_date": "2020-01-01T00:00:00",
  "end_date": "2025-12-31T00:00:00",
  "initial_capital": 100000
}
```

### Example `curl`

```bash
curl -X POST http://localhost:8005/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d @request.json
```

## Response Format

The API returns a `BacktestResponse` object (no `success/data` wrapper). Top-level fields:

- `parameters`
- `metrics`
- `equity_stats`
- `candles`
- `orders`

Notes:

- `orders[*]` uses frontend aliases: `symbol`, `action`, `shares`
- `candles[*].time` is a Unix timestamp (seconds)

## Strategy Requirements

User code must define a class inheriting from `hqg_algorithms.Strategy`.

Expected methods:

- `universe() -> list[str]`
- `on_data(data, portfolio) -> dict[str, float] | None`
- `cadence()` is optional if the base class provides a default

The strategy should return target portfolio weights (`sum(weights) <= 1.0`).

## Security / Sandbox Model

- AST static analysis (`src/execution/analysis.py`)
- Import/module allowlist + builtin/attribute blocklists
- Docker sandbox execution with:
  - `--network=none`
  - `--read-only`
  - memory / CPU / PID limits
  - dropped Linux capabilities

## Data Provider and Caching

Default provider: Yahoo Finance (`yfinance`) via `YFDataProvider`.

Behavior:

- Fetches daily OHLCV and stores per-symbol parquet cache in `data/cache/`
- Resamples to weekly/monthly/quarterly when requested by strategy cadence
- Uses symbol-level locks to avoid cache write races

## Middleware / Runtime Limits

Configured in `src/config/settings.py`:

- Request timeout (`MAX_REQUEST_TIME`, default 600s)
- Sandbox execution timeout (`MAX_EXECUTION_TIME`, default 300s)
- Rate limiting (per-minute and per-hour)
- Request body size limit (1 MB)
- Optional JWT auth middleware (enabled when `HQG_DASH_JWKS_URL` is set)

## Environment Variables

Common settings:

- `API_HOST` (default `0.0.0.0`)
- `API_PORT` (default `8000`)
- `HQG_DASH_JWKS_URL` (optional; enables auth middleware)
- `HQG_PROFILE=1` (optional; enables container profiling logs)

See `.env.example` for the base template.

## Testing

Run fast tests:

```bash
pytest -m "not integration"
```

Integration tests exercise the full pipeline and typically require:

- Docker
- network access (Yahoo Finance)
- longer execution times

## Project Layout

- `src/api/` FastAPI app, routes, middleware, handlers
- `src/execution/` validation + sandbox execution pipeline
- `src/services/data_provider/` market data providers (Yahoo + mock)
- `src/models/` request/response/execution/portfolio models
- `src/utils/metrics.py` performance metrics
- `tests/` route, execution, and strategy tests

## License

MIT License - see [LICENSE](LICENSE).
