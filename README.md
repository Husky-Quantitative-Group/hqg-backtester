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
- `metrics.sharpe_ratio` is returned under that alias (not `sharpe`)
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
