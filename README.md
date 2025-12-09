# HQG Backtester API

REST API service for running quantitative trading strategy backtests.

## Quick Start

### Using Docker (Recommended)

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`

### Manual Setup

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

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
  "code": "strategy code as string",
  "startDate": "2023-01-01",
  "endDate": "2023-12-31",
  "initialCash": 100000.0
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "summary": {...},
    "metrics": {...},
    "equityCurve": [...],
    "orders": [...]
  }
}
```

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

- **API Layer**: `api/main.py` - FastAPI endpoints
- **Backtest Engine**: `backtester/engine/backtester.py` - Core backtesting logic
- **Broker**: `backtester/execution/broker.py` - Order execution
- **Metrics**: `backtester/analysis/metrics.py` - Performance analysis
- **Data Manager**: `backtester/data/manager.py` - Market data fetching and caching
- **Database**: `data/` - DuckDB database for cached market data

## License

MIT License - see LICENSE file for details.

