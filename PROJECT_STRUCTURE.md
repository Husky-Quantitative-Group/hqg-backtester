# Project Structure Guide

Complete explanation of every directory and file in the HQG Backtester API project.

## Root Directory

```
hqg-backtester/
├── api/                    # API service layer
├── backtester/             # Backtesting engine
├── docker-compose.yml      # Docker orchestration
├── README.md              # Project documentation
├── LICENSE                # License file
├── .gitignore             # Git ignore rules
├── .dockerignore          # Docker ignore rules
└── .venv/                 # Python virtual environment (local dev only)
```

---

## `/api/` - API Service Layer

**Purpose**: FastAPI REST API that receives requests and returns backtest results.

### Files:

- **`main.py`** - Main FastAPI application
  - Defines `/health` and `/backtest` endpoints
  - Parses strategy code from requests
  - Formats and returns backtest results as JSON

- **`requirements.txt`** - Python dependencies for API
  - FastAPI, uvicorn (web server)
  - All backtester engine dependencies

- **`Dockerfile`** - Docker image definition
  - Builds containerized API service
  - Sets up Python environment and dependencies

- **`docker-compose.yml`** - Docker orchestration (at root)
  - Defines how to run the API container
  - Maps ports, volumes, environment variables

- **`build.sh`** - Build script
  - Helper script to build Docker image

- **`README.md`** - API documentation
  - How to use the API
  - Endpoint documentation

- **`example-request.json`** - Example API request
  - Sample JSON for testing the API

---

## `/backtester/` - Backtesting Engine

**Purpose**: Core backtesting logic - runs strategies, executes trades, calculates metrics.

### Structure:

```
backtester/
├── __init__.py           # Package initialization
├── runner.py             # High-level runner function
├── data_types.py         # Data structures (TradeBar, Slice)
├── engine/               # Backtest execution engine
├── execution/            # Order execution (broker)
├── analysis/             # Performance metrics
└── data/                 # Market data management (CODE ONLY)
    ├── manager.py
    ├── database.py
    └── sources/
```

### Key Files:

#### **`runner.py`**
- **Purpose**: High-level interface to run backtests
- **Used by**: API (`api/main.py` imports this)
- **What it does**: Creates Backtester instance, runs backtest, returns results

#### **`data_types.py`**
- **Purpose**: Defines data structures
- **Contains**: 
  - `TradeBar`: Single bar of OHLCV data
  - `Slice`: Collection of TradeBars for one timestamp

---

### `/backtester/engine/` - Backtest Execution

**Purpose**: Main backtest loop - processes each day, calls strategy, executes trades.

#### **`backtester.py`**
- **Purpose**: Core backtesting engine
- **What it does**:
  1. Gets market data for symbols
  2. Loops through each day
  3. Creates Slice with current market data
  4. Calls strategy's `on_data()` method
  5. Executes orders through broker
  6. Records equity curve
  7. Generates performance report

---

### `/backtester/execution/` - Order Execution

**Purpose**: Simulates broker - executes orders, tracks positions, calculates commissions.

#### **`broker.py`**
- **Purpose**: Simulates Interactive Brokers-style broker
- **What it does**:
  - Submits orders
  - Executes at market prices
  - Tracks cash and positions
  - Calculates commissions
  - Records fills (executed trades)

---

### `/backtester/analysis/` - Performance Metrics

**Purpose**: Calculates performance statistics from backtest results.

#### **`metrics.py`**
- **Purpose**: Performance analysis
- **Calculates**:
  - Returns (total, annualized)
  - Risk metrics (Sharpe, Sortino, max drawdown)
  - Trade metrics (win rate, profit factor)
  - Risk-adjusted returns (alpha, beta)

---

### `/backtester/data/` - Market Data Management

**Purpose**: Fetches, caches, and manages market data.

#### **`manager.py`** - Data Manager
- **Purpose**: High-level interface for getting market data
- **What it does**:
  1. Checks if data exists in database
  2. Downloads missing data from sources (yfinance, IBKR)
  3. Saves downloaded data to database
  4. Returns data as pandas DataFrames

#### **`database.py`** - Database Interface
- **Purpose**: DuckDB database operations
- **What it does**:
  - Creates database tables
  - Saves market data to database
  - Loads market data from database
  - Queries by symbol and date range

#### **`sources/`** - Data Source Implementations

**Purpose**: Interfaces to external data providers.

- **`base.py`** - Abstract base class for data sources
  - Defines interface all sources must implement
  - Normalizes data format (OHLCV columns)

- **`yfinance.py`** - Yahoo Finance data source
  - Downloads data from yfinance library
  - Used by default (free, no API key needed)

- **`ibkr.py`** - Interactive Brokers data source
  - Downloads from IBKR TWS/Gateway
  - Optional (requires IBKR account and running TWS)

---

### `/data/` - Database Storage (Root Level)

**Purpose**: Physical storage location for cached market data.

#### **`market_data.db`**
- **Type**: DuckDB database file
- **Location**: Root level `data/` directory (not inside `backtester/`)
- **Purpose**: Stores downloaded market data persistently
- **Why it exists**:
  - **Performance**: DB queries are faster than API calls
  - **Caching**: Avoids re-downloading same data
  - **Rate limits**: Reduces calls to yfinance/IBKR
  - **Offline**: Can run backtests without internet (if data cached)

**How it works**:
1. First request for AAPL 2023-01-01 to 2023-12-31
   - DataManager checks database → not found
   - Downloads from yfinance
   - Saves to `data/market_data.db`
2. Second request for same data
   - DataManager checks database → found!
   - Loads from database (fast, no download)
3. Request for overlapping data (e.g., 2023-06-01 to 2024-06-01)
   - DataManager checks database → has 2023 data
   - Only downloads missing 2024 data
   - Merges with existing data

---

## Relationship: `/backtester/data/` vs `/data/`

### `/backtester/data/` - Code (Logic)
- **Contains**: Python code for managing data
- **Purpose**: Logic for fetching, caching, storing data
- **Files**: `manager.py`, `database.py`, `sources/`
- **Analogy**: The "librarian" - knows how to find and organize books

### `/data/` - Data (Storage) - Root Level
- **Contains**: Actual database file with market data
- **Purpose**: Persistent storage of downloaded data
- **File**: `data/market_data.db` (DuckDB database)
- **Location**: Root level (separate from code)
- **Analogy**: The "library shelves" - where books are actually stored

**Why separate?**
- **Clean separation**: Code and data are separate
- **Easy backup**: Can backup `data/` independently
- **Git-friendly**: Data is in `.gitignore`, code is versioned
- **Docker-friendly**: Can mount `data/` as volume separately

**Flow**:
```
API Request
    ↓
Backtester Engine
    ↓
DataManager (in backtester/data/)
    ↓
Database (checks /data/) ← Checks if data exists
    ↓
If missing → Data Source (yfinance/IBKR) → Download
    ↓
Save to Database (in /data/)
    ↓
Return data to Backtester
```

---

## Configuration Files

### **`docker-compose.yml`** (root)
- **Purpose**: Docker orchestration
- **Defines**: How to run the API container
- **Maps**: Port 8000, database volume

### **`.gitignore`**
- **Purpose**: Files Git should ignore
- **Ignores**: `__pycache__/`, `.venv/`, `*.db`, etc.

### **`.dockerignore`**
- **Purpose**: Files Docker should ignore when building
- **Ignores**: `.git/`, `.venv/`, test files, etc.

### **`LICENSE`**
- **Purpose**: Legal license (MIT)

---

## Data Flow Summary

```
1. Dashboard → POST /backtest (with strategy code)
   ↓
2. api/main.py → Parses code, extracts universe
   ↓
3. backtester/runner.py → Creates Backtester
   ↓
4. backtester/engine/backtester.py → Runs backtest
   ↓
5. backtester/data/manager.py → Gets market data
   ↓
6. backtester/data/database.py → Checks data/market_data.db
   ↓
7. If missing → backtester/data/sources/yfinance.py → Downloads
   ↓
8. Saves to data/market_data.db
   ↓
9. Returns data → Backtester processes it
   ↓
10. backtester/execution/broker.py → Executes trades
   ↓
11. backtester/analysis/metrics.py → Calculates metrics
   ↓
12. api/main.py → Formats response
   ↓
13. Dashboard ← JSON response
```

---

## Why Two Folders?

**`/backtester/data/`** = The system (code)
- How to get data
- How to store data
- How to retrieve data

**`/data/`** = The storage (data) - at root level
- Where data lives
- Actual database file
- Persists between runs

**Analogy**: 
- `/backtester/data/` = The library system (catalog, checkout system)
- `/data/` = The actual books on shelves

You need both:
- Code (`/backtester/data/`) to manage the data
- Storage (`/data/`) to persist the data

