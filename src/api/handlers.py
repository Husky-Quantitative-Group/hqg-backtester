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
from ..utils.metrics import calculate_metrics
from ..execution.orchestrator import Orchestrator
from ..scheduler.kv_store import kv_store
from ..scheduler.job_store import job_store
from ..scheduler.queue import job_queue

logger = logging.getLogger(__name__)


class BacktestHandler:

    def __init__(self):
        self.orchestrator = Orchestrator()

    async def handle_backtest(self, request: BacktestRequest) -> BacktestResponse:

        # Register job
        job_id = str(uuid.uuid4())
        await kv_store.set(job_id, request)
        await job_store.create(job_id)
        await job_queue.put(job_id)

        # Pick from queue
        # NOTE: Once scheduler + container pool is implemented,
        # we will handle this via scheduling instead of just dequeueing directly.
        queued_id = await job_queue.get()
        queued_request = await kv_store.get(queued_id)
        await job_store.set_running(queued_id)

        try:
            logger.info(f"Starting backtest [{queued_id}]: {queued_request.start_date} to {queued_request.end_date}")

            raw_result = await self.orchestrator.run(queued_request)
            await job_store.set_completed(queued_id)

        except Exception:
            await job_store.set_failed(queued_id)
            raise
        # garbage collection
        finally:
            await kv_store.delete(queued_id)

        # Build response (unchanged shape)
        trades = [Trade(**t) for t in raw_result.trades]

        equity_curve_dt = {
            datetime.fromisoformat(ts): val
            for ts, val in raw_result.equity_curve.items()
        }

        metrics = calculate_metrics(
            equity_curve_data=equity_curve_dt,
            trades=trades,
            initial_capital=queued_request.initial_capital,
            data_provider=self.orchestrator.data_provider,
            bar_size=raw_result.bar_size,
        )

        logger.info(f"Backtest [{queued_id}] complete. Sharpe: {metrics.sharpe:.2f}")

        net_profit = raw_result.final_value - queued_request.initial_capital
        total_volume = sum(t.price * t.amount for t in trades)

        candles = [
            EquityCandle(
                time=int(datetime.fromisoformat(ts).timestamp()),
                **ohlc_vals,
            )
            for ts, ohlc_vals in raw_result.ohlc.items()
        ]

        return BacktestResponse(
            job_id=queued_id,
            parameters=BacktestParameters(
                name=queued_request.name or "Unnamed Backtest",
                starting_equity=queued_request.initial_capital,
                start_date=queued_request.start_date,
                end_date=queued_request.end_date,
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
