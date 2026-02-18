from fastapi import APIRouter, HTTPException
from ..models.request import BacktestRequest, ValidationException, ExecutionException
from ..models.response import BacktestResponse
from .handlers import BacktestHandler


router = APIRouter(prefix="/api/v1")
handler = BacktestHandler()


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest_endpoint(request: BacktestRequest):
    """
    Run a backtest with user-provided strategy code.

    BacktestRequest
    - strategy_code: Python code defining a Strategy subclass
    - start_date: Backtest start date
    - end_date: Backtest end date
    - initial_capital: Starting capital (default: 10000)
    """
    try:
        result = await handler.handle_backtest(request)
        return result
    except ValidationException as e:
        # Analysis errors, displayed in code editor
        raise HTTPException(status_code=400, detail={"analysis_errors": e.errors.errors})
    except ExecutionException as e:
        # Execution errors, displayed as traceback
        raise HTTPException(status_code=400, detail={"execution_errors": e.errors.errors})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")



# TODO: how is the robust version going to be used? on a different page for the backtester? or layout/chart determined by 
#   response? bc this will return dif stuff (eg, multiple paths to plot and/or 80/20 confidence bands)

# @router.post("/backtest-advanced", response_model=BacktestResponse)
# async def run_backtest(request: BacktestRequest):
#     try:
#         result = await backtester.execute(request)
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
