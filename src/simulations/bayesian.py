import asyncio
import logging

import numpy as np
from skopt import Optimizer
from skopt.space import Integer, Real

from .base import BaseSimulation
from ..models.request import BacktestRequest, BacktestRequestError, ExecutionException
from ..models.simulation import SimulationRun, SimulationResponse

logger = logging.getLogger(__name__)

class BayesianSimulation(BaseSimulation):
    async def run(self, job_id: str, request: BacktestRequest) -> SimulationResponse:
        logger.info(f"Bayesian [{job_id}] starting")

        config = request.config_params or {}
        objective = config.get("objective", "sharpe")
        n_initial = int(config.get("n_initial", 10))
        n_iterations = int(config.get("n_iterations", 50))
        param_space = config.get("params", {})

        # Build skopt search space
        param_names = list(param_space.keys())
        dimensions = []
        for name in param_names:
            spec = param_space[name]
            if spec["type"] == "int":
                dimensions.append(Integer(spec["min"], spec["max"], name=name))
            else:
                dimensions.append(Real(spec["min"], spec["max"], name=name))

        optimizer = Optimizer(
            dimensions=dimensions,
            acq_func="gp_hedge",
            random_state=42,
            n_initial_points=0,
        )

        rng = np.random.RandomState(42)
        initial_params_list = []
        for _ in range(n_initial):
            point = {}
            for name in param_names:
                spec = param_space[name]
                if spec["type"] == "int":
                    point[name] = int(rng.randint(spec["min"], spec["max"] + 1))
                else:
                    point[name] = float(rng.uniform(spec["min"], spec["max"]))
            initial_params_list.append(point)

        initial_results = await asyncio.gather(
            *[self._run_one(request, p) for p in initial_params_list]
        )

        runs = []
        initial_x = []
        initial_y = []

        for params, response in initial_results:
            x_point = [params[n] for n in param_names]
            if response is not None:
                score = self._get_score(response, objective)
                runs.append(SimulationRun(config_params=params, result=response))
            else:
                score = float("-inf")
            initial_x.append(x_point)
            initial_y.append(-score)

        await asyncio.to_thread(optimizer.tell, initial_x, initial_y)

        for _ in range(n_iterations):
            next_x = optimizer.ask()

            params = {
                name: int(value) if isinstance(dim, Integer) else value
                for name, value, dim in zip(param_names, next_x, dimensions)
            }

            _, response = await self._run_one(request, params)

            score = self._get_score(response, objective) if response is not None else float("-inf")
            if response is not None:
                runs.append(SimulationRun(config_params=params, result=response))

            await asyncio.to_thread(optimizer.tell, [next_x], [-score])

        if not runs:
            errors = BacktestRequestError()
            errors.add("All Bayesian optimisation runs failed; no successful results to return")
            raise ExecutionException(errors)

        result = self._build_response(job_id, "bayes", runs, objective)
        logger.info(f"Bayesian [{job_id}] complete: {len(runs)}/{n_initial + n_iterations} runs succeeded")
        return result
