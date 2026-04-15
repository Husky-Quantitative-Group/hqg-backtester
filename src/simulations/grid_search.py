import asyncio
import itertools
import logging

from .base import BaseSimulation
from ..models.request import BacktestRequest, BacktestRequestError, ExecutionException
from ..models.simulation import SimulationRun, SimulationResponse

logger = logging.getLogger(__name__)


class GridSearchSimulation(BaseSimulation):
    async def run(self, job_id: str, request: BacktestRequest) -> SimulationResponse:
        logger.info(f"GridSearch [{job_id}] starting")

        config = request.config_params or {}
        objective = config.get("objective", "sharpe")
        param_space = config.get("params", {})

        keys = list(param_space.keys())
        combinations = [
            dict(zip(keys, values))
            for values in itertools.product(*param_space.values())
        ]

        results = await asyncio.gather(
            *[self._run_one(request, params) for params in combinations]
        )

        runs = [
            SimulationRun(config_params=params, result=response)
            for params, response in results
            if response is not None
        ]

        if not runs:
            errors = BacktestRequestError()
            errors.add("All grid search runs failed; no successful results to return")
            raise ExecutionException(errors)

        result = self._build_response(job_id, "grid", runs, objective)
        logger.info(f"GridSearch [{job_id}] complete: {len(runs)}/{len(combinations)} runs succeeded")
        return result
