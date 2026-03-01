import logging
import uuid
from datetime import datetime
from ..models.request import BacktestRequest
from ..models.response import (
    BacktestResponse,
    BacktestParameters,
    EquityStats,
    EquityCandle,
    Trade,
)
from ..scheduler.kv_store import kv_store
from ..scheduler.job_store import job_store
from ..scheduler.queue import job_queue
from ..utils.metrics import calculate_metrics
from ..execution.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

class BacktestHandler:
    def __init__(self):
        self.orchestrator = Orchestrator()

    # run a synchronous backtest, no scheduling. used for profiling purposes
    async def run_backtest(self, request: BacktestRequest) -> BacktestResponse:
        try:
            logger.info(f"Starting backtest via orchestrator: {request.start_date} to {request.end_date}")

            # Run full validation pipeline (parse → fetch → execute → validate)
            raw_result = await self.orchestrator.run(request)

            # Reconstruct Trade objects from raw dicts
            trades = [Trade(**t) for t in raw_result.trades]

            # Parse equity curve keys back to datetime for metrics calculation
            equity_curve_dt = {
                datetime.fromisoformat(ts): val
                for ts, val in raw_result.equity_curve.items()
            }

            # Compute metrics (single source of truth, after validation)
            metrics = calculate_metrics(
                equity_curve_data=equity_curve_dt,
                trades=trades,
                initial_capital=request.initial_capital,
                data_provider=self.orchestrator.data_provider,
                bar_size=raw_result.bar_size,
            )

            logger.info(f"Backtest complete. Sharpe: {metrics.sharpe:.2f}")

            # Transform to frontend response format
            net_profit = raw_result.final_value - request.initial_capital
            total_volume = sum(t.price * t.amount for t in trades)

            candles = [
                EquityCandle(
                    time=int(datetime.fromisoformat(ts).timestamp()),
                    **ohlc_vals,
                )
                for ts, ohlc_vals in raw_result.ohlc.items()
            ]

            return BacktestResponse(
                parameters=BacktestParameters(
                    name=request.name or "Unnamed Backtest",
                    starting_equity=request.initial_capital,
                    start_date=request.start_date,
                    end_date=request.end_date,
                ),
                metrics=metrics,
                equity_stats=EquityStats(
                    equity=raw_result.final_value,
                    fees=0.0,  # TODO: implement fee tracking in portfolio
                    net_profit=net_profit,
                    return_pct=metrics.total_return * 100,
                    volume=total_volume,
                ),
                candles=candles,
                orders=trades,
            )

        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}", exc_info=True)
            raise
        
    async def submit_backtest(self, request: BacktestRequest) -> str:
        job_id = str(uuid.uuid4())
        await kv_store.set(job_id, request)
        await job_store.create(job_id)
        await job_queue.put(job_id)
        return job_id
