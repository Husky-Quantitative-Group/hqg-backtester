# Project Structure

## Overview

```
hqg-backtester/
├── src/                      # Main application source code
│   ├── api/                  # FastAPI REST endpoints
│   ├── config/               # Configuration management
│   ├── models/               # Pydantic models (requests/responses)
│   ├── services/             # Business logic layer
│   ├── strategies/           # Cached Strategy code
│   └── utils/                # Utilities (metrics, validators, etc.)
├── tests/                    # Unit and integration tests
├── docker-compose.yml
├── requirements.txt
├── usage.py                  # Example usage script
├── README.md
└── LICENSE
```

## `/src/api/` - REST API Layer

FastAPI endpoints for the backtester service.

- **`server.py`** - FastAPI application instance with middleware
- **`routes.py`** - API endpoint definitions (`POST /api/v1/backtest`)
- **`handlers.py`** - Request handling logic
- **`middleware.py`** - Custom middleware (timeouts, rate limiting, size limits)

## `/src/services/` - Business Logic

Core backtesting and data management services.

- **`backtester.py`** - Main `Backtester` class
  - Orchestrates strategy execution
  - Manages portfolio state
  - Calculates metrics and equity curve
  - Depends on `hqg-algorithms` Strategy interface

- **`data_provider/`** - Market data abstraction
  - **`base_provider.py`** - Abstract `DataProvider` interface
  - **`yf_provider.py`** - Yahoo Finance implementation (default)
  - **`mock_provider.py`** - Mock provider for testing

## `/src/models/` - Request/Response Models

Pydantic models for API contracts.

- **`request.py`** - `BacktestRequest` (strategy code, dates, capital)
- **`response.py`** - `BacktestResponse` (metrics, equity curve, trades)
- **`portfolio.py`** - `Portfolio` class (tracks positions and cash)

## `/src/config/` - Configuration

- **`settings.py`** - Some application settings.
- **`.env`** - Secrets, etc.

## `/src/utils/` - Utilities

- **`metrics.py`** - Performance calculation functions
- **`strategy_loader.py`** - Strategy code loading/validation
- **`validators.py`** - Input validation helpers

## `/tests/` - Test Suite

- **`test_backtester.py`** - Backtester service tests
- **`test_routes.py`** - API endpoint tests


## Data Flow (more or less)

```
POST /api/v1/backtest (with strategy_code, dates, capital)
  ↓
src/api/routes.py → handlers.py (parse request)
  ↓
Backtester.run():
  DataProvider.get_data()
  for slice in data:
    desired_allocations = Strategy.on_data(slice)
    Portfolio.update(desired_allocations)
  ↓
calculate_metrics()
  ↓
BacktestResponse (trades, metrics, equity curve)
```
