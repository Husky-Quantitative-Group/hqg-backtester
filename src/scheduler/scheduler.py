import asyncio
import logging
from datetime import datetime

from ..models.jobs import JobStatus
from ..models.response import (
    BacktestResponse,
    BacktestParameters,
    EquityStats,
    EquityCandle,
    Trade,
)
from ..utils.metrics import calculate_metrics
from ..execution.orchestrator import Orchestrator
from ..models.execution import RawExecutionResult
from ..models.request import BacktestRequest
from ..services.data_provider.base_provider import BaseDataProvider
from .kv_store import kv_store
from .job_store import job_store
from .queue import job_queue

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self._orchestrator = Orchestrator()

    async def run(self) -> None:
        """Background consumer loop. Runs for the lifetime of the server."""
        logger.info("Scheduler started")
        while True:
            job_id = await job_queue.get()
            record = await job_store.get(job_id)
            if record is None or record.status == JobStatus.CANCELLED:
                logger.debug(f"Skipping cancelled/evicted job [{job_id}]")
                continue
            asyncio.create_task(self._execute_job(job_id))

    async def _execute_job(self, job_id: str) -> None:
        request = await kv_store.get(job_id)
        if request is None:
            # Cancelled between dequeue and task start
            return

        await job_store.set_running(job_id)
        logger.info(f"Executing job [{job_id}]: {request.start_date} to {request.end_date}")

        try:
            raw_result = await self._orchestrator.run(request)
            response = self._build_response(job_id, request, raw_result, self._orchestrator.data_provider)
            await job_store.set_completed(job_id, response)
            logger.info(f"Job [{job_id}] completed. Sharpe: {response.metrics.sharpe:.2f}")
        except Exception as e:
            await job_store.set_failed(job_id, str(e))
            logger.error(f"Job [{job_id}] failed: {e}")
        finally:
            await kv_store.delete(job_id)
    def _build_response(
        self,
        job_id: str,
        request: BacktestRequest,
        raw_result: RawExecutionResult,
        data_provider: BaseDataProvider,
        ) -> BacktestResponse:
            trades = [Trade(**t) for t in raw_result.trades]

            equity_curve_dt = {
                datetime.fromisoformat(ts): val
                for ts, val in raw_result.equity_curve.items()
            }

            metrics = calculate_metrics(
                equity_curve_data=equity_curve_dt,
                trades=trades,
                initial_capital=request.initial_capital,
                data_provider=data_provider,
                bar_size=raw_result.bar_size,
            )

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
                job_id=job_id,
                parameters=BacktestParameters(
                    name=request.name or "Unnamed Backtest",
                    starting_equity=request.initial_capital,
                    start_date=request.start_date,
                    end_date=request.end_date,
                ),
                metrics=metrics,
                equity_stats=EquityStats(
                    equity=raw_result.final_value,
                    fees=0.0,
                    net_profit=net_profit,
                    return_pct=metrics.total_return * 100,
                    volume=total_volume,
                ),
                candles=candles,
                orders=trades,
            )

scheduler = Scheduler()
