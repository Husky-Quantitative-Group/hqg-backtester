# Backtester API

REST API for running quantitative trading strategy backtests with sandboxed execution.

## Quick Start

```bash
# Build worker image
./build-worker.sh

# Start production services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Stop services
docker-compose down
```

The API will be available at `http://localhost:8000`

## Architecture

- **FastAPI Server**: Validates requests, downloads data, spawns worker containers
- **Worker Containers**: Isolated Docker containers that execute user strategies
- **Security**: RestrictedPython + hardened Docker (no network, read-only, resource limits)
- **Concurrency**: Max 3 simultaneous backtests with file locking for data downloads

## API Endpoints

### Health Check
```
GET /health
```

### Run Backtest
```
POST /backtest
```

**Request Body:**
```json
{
  "code": "class MyStrategy(Strategy): ...",
  "tickers": ["SPY", "QQQ"],
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_cash": 100000.0,
  "commission_rate": 0.005,
  "parameters": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "initialCash": 100000.0,
      "finalEquity": 125000.0,
      "totalReturn": 25.0,
      "numTrades": 42
    },
    "metrics": {
      "sharpeRatio": 1.5,
      "maxDrawdown": 5.2,
      "winRate": 60.0
    },
    "equityCurve": [...],
    "orders": [...]
  }
}
```

## Example Strategy

```python
from hqg_algorithms import Strategy, Cadence

class MomentumStrategy(Strategy):
    def universe(self):
        return ['SPY']

    def cadence(self):
        return Cadence()

    def on_data(self, slice, portfolio):
        spy = slice.get('SPY')
        if spy and spy.close > spy.open:
            return {'SPY': 1.0}  # 100% allocation
        return {'SPY': 0.0}  # No allocation
```

## Security Features

- **RestrictedPython**: Blocks imports, file I/O, system calls at compile-time
- **Docker Isolation**: `--network=none`, `--read-only`, `--cap-drop=ALL`
- **Resource Limits**: 512MB RAM, 1 CPU core, 100 process limit per backtest
- **Concurrency Control**: Max 3 concurrent backtests, file locking for downloads
- **Automatic Cleanup**: Worker containers deleted after execution

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Integration Example

```javascript
const response = await fetch('http://localhost:8000/backtest', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: strategyCode,
    tickers: ['SPY', 'QQQ'],
    start_date: '2023-01-01',
    end_date: '2023-12-31',
    initial_cash: 100000,
    commission_rate: 0.005
  })
});

const result = await response.json();
if (result.success) {
  console.log(result.data.summary);
}
```
