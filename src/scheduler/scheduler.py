import asyncio
import logging

from ..models.jobs import JobStatus
from ..execution.orchestrator import Orchestrator
from .kv_store import kv_store
from .job_store import job_store
from .queue import job_queue
from ..utils.build_response import build_backtest_response
from ..config.log_handler import current_job_id
from ..simulations.grid_search import GridSearchSimulation
from ..simulations.bayesian import BayesianSimulation

logger = logging.getLogger(__name__)

_SIMULATION_MAP = {
    "grid": GridSearchSimulation,
    "bayes": BayesianSimulation,
}


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

        sim_type = (request.config_params or {}).get("simulation")

        if sim_type is not None:
            await self._execute_simulation(job_id, sim_type, request)
        else:
            await self._execute_backtest(job_id, request)

        await kv_store.delete(job_id)

    async def _execute_backtest(self, job_id: str, request) -> None:
        logger.info(f"Executing job [{job_id}]: {request.start_date} to {request.end_date}")
        try:
            raw_result = await self._orchestrator.run(request)
            response = build_backtest_response(job_id, request, raw_result, self._orchestrator.data_provider)
            for msg in raw_result.strategy_logs:
                job_store.append_log(job_id, msg)
            await job_store.set_completed(job_id, response)
            logger.info(f"Job [{job_id}] completed. Sharpe: {response.metrics.sharpe:.2f}")
        except Exception as e:
            job_store.append_log(job_id, str(e))
            await job_store.set_failed(job_id, str(e))
            logger.error(f"Job [{job_id}] failed: {e}")

    async def _execute_simulation(self, job_id: str, sim_type: str, request) -> None:
        sim_class = _SIMULATION_MAP.get(sim_type)
        if sim_class is None:
            await job_store.set_failed(job_id, f"Unknown simulation type: '{sim_type}'")
            return

        logger.info(f"Executing simulation [{job_id}] type={sim_type}")
        try:
            result = await sim_class().run(job_id, request)
            await job_store.set_completed(job_id, result)
            logger.info(f"Simulation [{job_id}] complete. Best {result.simulation_type} params: {result.best_params}")
        except Exception as e:
            await job_store.set_failed(job_id, str(e))
            logger.error(f"Simulation [{job_id}] failed: {e}")


scheduler = Scheduler()
