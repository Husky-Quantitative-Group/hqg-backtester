# HQG Backtester API

A FastAPI-based service for running quantitative trading strategy backtests.

## Quick Start

### Docker (Recommended)

```bash
docker-compose up --build
```

API available at `http://localhost:8000`

### Manual Setup

```bash
pip install -r requirements.txt
python -m src.api.server
```

Or with uvicorn:

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

## API Usage

### Health Check

```
GET http://localhost:8000/health
```

### Run Backtest

```
POST http://localhost:8000/api/v1/backtest
Content-Type: application/json

{
  "strategy_code": "class MyStrategy(Strategy):\n  def universe(self):\n    return ['SPY', 'TLT']\n  def cadence(self):\n    return Cadence()\n  def on_data(self, data, portfolio):\n    return {'SPY': 0.6, 'TLT': 0.4}",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 100000
}
```

### Response

```json
{
  "success": true,
  "data": {
    "final_value": 125000,
    "metrics": {
      "total_return": 0.25,
      "annualized_return": 0.25,
      "max_drawdown": -0.15,
      "sharpe_ratio": 1.2
    },
    "equity_curve": [100000, 101000, 102500, ...],
    "trades": [...]
  }
}
```

## Documentation

- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Creating a Strategy

Strategies inherit from `hqg_algorithms.Strategy`:

```python
from hqg_algorithms import Strategy, Cadence

class MyStrategy(Strategy):
    def universe(self):
        """Return list of symbols to trade"""
        return ["SPY", "TLT", "GLD"]
    
    def cadence(self):
        """Return trading frequency"""
        return Cadence()  # Daily by default
    
    def on_data(self, data, portfolio):
        """Called each period with market data"""
        # Return dict of {symbol: weight} for rebalancing
        return {"SPY": 0.5, "TLT": 0.3, "GLD": 0.2}
```

## Architecture

- **API**: src/api/ - FastAPI routes and middleware
- **Services**: src/services/ - Backtester logic and data providers
- **Models**: src/models/ - Pydantic schemas
- **Tests**: tests/ - Unit and integration tests

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed architecture.

## Requirements

- Python 3.10+
- Dependencies in [requirements.txt](requirements.txt)

## License

MIT License - see [LICENSE](LICENSE) file.

