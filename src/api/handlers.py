import logging
import uuid

from ..models.request import BacktestRequest
from ..models.response import BacktestResponse
from ..scheduler.kv_store import kv_store
from ..scheduler.job_store import job_store
from ..scheduler.queue import job_queue
from ..execution.orchestrator import Orchestrator
from ..utils.build_response import build_backtest_response

logger = logging.getLogger(__name__)

class BacktestHandler:
    def __init__(self):
        self.orchestrator = Orchestrator()

    # run a synchronous backtest, no scheduling. used for profiling purposes
    async def run_backtest(self, request: BacktestRequest) -> BacktestResponse:
        try:
            logger.info(f"Starting backtest via orchestrator: {request.start_date} to {request.end_date}")

            # parse -> fetch -> execute -> validate
            raw_result = await self.orchestrator.run(request)

            response = build_backtest_response("NA", request, raw_result, self.orchestrator.data_provider)
            return response

        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}", exc_info=True)
            raise
        
    async def submit_backtest(self, request: BacktestRequest) -> str:
        job_id = str(uuid.uuid4())
        await kv_store.set(job_id, request)
        await job_store.create(job_id)
        await job_queue.put(job_id)
        return job_id
