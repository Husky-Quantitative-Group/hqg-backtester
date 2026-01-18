from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
from pathlib import Path
import sys
import os
import subprocess
import traceback
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtester.data.manager import DataManager
from helpers import (
    parse_date_from_string,
    validate_strategy_structure,
    validate_tickers,
    parse_strategy_code_safe,
    format_results_for_frontend,
    download_data_with_lock,
)
from docker_runner import run_backtest_in_docker

app = FastAPI(
    title="HQG Backtester API",
    description="REST API for running quantitative trading strategy backtests",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize data manager for pre-downloading data
DATA_PATH = Path(__file__).parent.parent / "data"
data_manager = DataManager(storage_path=str(DATA_PATH))
BACKTEST_SEMAPHORE = asyncio.Semaphore(3) # Limit concurrent backtests to 3 to prevent resource exhaustion


class BacktestRequest(BaseModel):
    code: str = Field(..., description="Strategy code (must subclass Strategy)", max_length=50_000)
    tickers: list[str] = Field(..., description="List of ticker symbols", min_length=1, max_length=50)
    start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)", pattern=r'^\d{4}-\d{2}-\d{2}$')
    end_date: str | None = Field(None, description="End date (YYYY-MM-DD)", pattern=r'^\d{4}-\d{2}-\d{2}$')
    initial_cash: float = Field(100000.0, description="Starting capital", gt=0, le=100_000_000)
    commission_rate: float = Field(0.005, description="Commission rate", ge=0, le=0.1)
    parameters: dict[str, Any] | None = Field(None, description="Custom parameters passed to strategy")


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/backtest")
async def backtest(request: BacktestRequest):
    try:
        # 1. Validate code structure
        is_valid, error = validate_strategy_structure(request.code)
        if not is_valid:
            return {"success": False, "error": error}

        # 2. Validate and normalize tickers
        tickers, error = validate_tickers(request.tickers)
        if error:
            return {"success": False, "error": error}

        # 3. Parse dates with defaults
        start_date = parse_date_from_string(request.start_date, datetime(2019, 1, 3))
        end_date = parse_date_from_string(request.end_date, datetime(2025, 1, 3))

        # 4. Validate date range
        if end_date <= start_date:
            return {"success": False, "error": "End date must be after start date"}

        # 5. Validate that code can be compiled safely
        # (Docker worker will do the actual compilation, but we check here for early errors)
        try:
            _ = parse_strategy_code_safe(request.code, request.parameters)
        except ValueError as e:
            return {"success": False, "error": f"Strategy parsing error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error parsing strategy: {str(e)}"}

        # 6-7. Download data and run backtest with concurrency limit
        # Semaphore ensures max 3 concurrent backtests to prevent resource exhaustion
        async with BACKTEST_SEMAPHORE:
            # Download data with file locking (prevents corruption from concurrent downloads)
            try:
                await asyncio.to_thread(
                    download_data_with_lock,
                    data_manager,
                    DATA_PATH / ".download.lock",
                    tickers,
                    start_date,
                    end_date,
                )
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to download market data: {str(e)}"
                }

            # Run backtest in hardened Docker container
            try:
                results = await asyncio.to_thread(
                    run_backtest_in_docker,
                    code=request.code,
                    tickers=tickers,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=request.initial_cash,
                    commission_rate=request.commission_rate,
                    parameters=request.parameters,
                    timeout=300,  # 5 minutes
                )
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Backtest execution timeout (exceeded 5 minutes)"
                }
            except RuntimeError as e:
                return {
                    "success": False,
                    "error": f"Docker execution error: {str(e)}"
                }

        # 8. Format results for frontend
        formatted_data = format_results_for_frontend(
            results=results,
            initial_cash=request.initial_cash,
            start_date=start_date,
        )

        return {
            "success": True,
            "data": formatted_data,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
