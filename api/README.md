# Backtester API

REST API for running quantitative trading strategy backtests.

## Quick Start

### Using Docker (Recommended)

```bash
# Build and run
docker-compose up --build

# Or just run (if already built)
docker-compose up
```

The API will be available at `http://localhost:8000`

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
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
  "startDate": "2023-01-01",  // Optional, defaults to 2020-01-03
  "endDate": "2023-12-31",    // Optional, defaults to 2024-01-03
  "initialCash": 100000.0     // Optional, defaults to 100000.0
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
      "numTrades": 42,
      ...
    },
    "metrics": {
      "sharpeRatio": 1.5,
      "maxDrawdown": 5.2,
      ...
    },
    "equityCurve": [...],
    "orders": [...]
  }
}
```

## Example Request

```bash
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d @example-request.json
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Integration with Dashboard

Your dashboard can make requests like:

```javascript
const response = await fetch('http://localhost:8000/backtest', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    code: strategyCode,
    startDate: '2023-01-01',
    endDate: '2023-12-31',
    initialCash: 100000
  })
});

const result = await response.json();
if (result.success) {
  // Use result.data.summary, result.data.metrics, etc.
}
```

