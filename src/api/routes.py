from fastapi import APIRouter, HTTPException
from ..models.request import BacktestRequest#, BacktestAdvancedRequest (TODO)
from ..models.response import BacktestResponse#, BacktestAdvancedResponse (TODO)
from .handlers import BacktestHandler


router = APIRouter(prefix="/api/v1")
handler = BacktestHandler()     # so backtester pure

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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
