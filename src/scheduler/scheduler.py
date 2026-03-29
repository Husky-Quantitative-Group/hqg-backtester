import asyncio
import logging

from ..models.jobs import JobStatus
from ..execution.orchestrator import Orchestrator
from .kv_store import kv_store
from .job_store import job_store
from .queue import job_queue
from ..utils.build_response import build_backtest_response
from ..config.log_handler import current_job_id

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
        current_job_id.set(job_id)

        request = await kv_store.get(job_id)
        if request is None:
            # Cancelled between dequeue and task start
            return

        await job_store.set_running(job_id)
        logger.info(f"Executing job [{job_id}]: {request.start_date} to {request.end_date}")

        try:
            raw_result = await self._orchestrator.run(request)
            response = build_backtest_response(job_id, request, raw_result, self._orchestrator.data_provider)
            await job_store.set_completed(job_id, response)
            logger.info(f"Job [{job_id}] completed. Sharpe: {response.metrics.sharpe:.2f}")
        except Exception as e:
            await job_store.set_failed(job_id, str(e))
            logger.error(f"Job [{job_id}] failed: {e}")
        finally:
            await kv_store.delete(job_id)


scheduler = Scheduler()
