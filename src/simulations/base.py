import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from ..models.request import BacktestRequest
from ..models.response import BacktestResponse
from ..models.simulation import SimulationRun, SimulationResponse
from ..execution.orchestrator import Orchestrator
from ..utils.build_response import build_backtest_response
from ..config.settings import settings

logger = logging.getLogger(__name__)


class BaseSimulation:
    """
    Shared infrastructure for simulation orchestrators.

    Uses a simulation-scoped Orchestrator (separate semaphore) so simulation
    fan-outs don't compete with individual backtests for container slots.
    """

    def __init__(self):
        self._orchestrator = Orchestrator(semaphore=asyncio.Semaphore(settings.SIMULATION_CONCURRENCY))

    async def _run_one(
        self,
        request: BacktestRequest,
        params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Optional[BacktestResponse]]:
        """
        Run a single backtest with the given resolved params dict.
        Wraps params under the standard "params" key before passing to orchestrator.
        Returns (params, response) or (params, None) on failure.
        """
        run_request = request.model_copy(update={"config_params": {"params": params}})
        try:
            raw = await self._orchestrator.run(run_request)
            response = build_backtest_response("sim", run_request, raw, self._orchestrator.data_provider)
            return params, response
        except Exception as e:
            logger.warning(f"Simulation run failed for params {params}: {e}")
            return params, None

    def _get_score(self, response: BacktestResponse, objective: str) -> float:
        if not hasattr(response.metrics, objective):
            raise ValueError(f"Unknown objective '{objective}'")
        value = getattr(response.metrics, objective)
        return float(value) if value is not None else 0.0

    def _build_response(
        self,
        job_id: str,
        sim_type: str,
        runs: List[SimulationRun],
        objective: str,
    ) -> SimulationResponse:
        runs.sort(key=lambda sr: self._get_score(sr.result, objective), reverse=True)
        best = runs[0]
        return SimulationResponse(
            job_id=job_id,
            simulation_type=sim_type,
            best_params=best.config_params,
            best_metrics=best.result.metrics,
            runs=runs,
            total_runs=len(runs),
        )

