import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from hqg_algorithms import extract_metadata

from ..models.request import BacktestRequest, ValidationException, ExecutionException
from ..models.execution import ExecutionPayload
from ..models.response import BacktestResponse
from ..models.simulation import SimulationRun, SimulationResponse
from ..execution.analysis import StaticAnalyzer
from ..execution.executor import Executor
from ..execution.output_validator import OutputValidator
from ..execution.orchestrator import dataframe_to_json
from ..services.data_provider.yf_provider import YFDataProvider
from ..utils.build_response import build_backtest_response

logger = logging.getLogger(__name__)

# Separate from Orchestrator._semaphore so simulations don't crowd out regular backtests
_simulation_semaphore = asyncio.Semaphore(5)

OBJECTIVE_FIELDS = {
    "sharpe": lambda m: m.sharpe,
    "sortino": lambda m: m.sortino,
    "total_pct_return": lambda m: m.total_pct_return,
    "calmar": lambda m: m.calmar or 0.0,
    "annualized_return": lambda m: m.annualized_return or 0.0,
}


class BaseSimulation:
    """
    Shared infrastructure for simulation orchestrators.

    Subclasses implement run() with their own combination strategy, but
    share _prepare(), _run_one(), and _build_response() from here.
    """

    def __init__(self):
        self.data_provider = YFDataProvider()
        self.executor = Executor()
        self.output_validator = OutputValidator()

    async def _prepare(self, request: BacktestRequest) -> Tuple[list, Any, Dict[str, Any]]:
        """
        Static analysis, strategy metadata extraction, and data fetch.
        Returns (universe, cadence, market_data_json).
        Called once per simulation — all N runs share this data.
        """
        StaticAnalyzer.analyze(request)
        if not request.errors.is_empty():
            raise ValidationException(request.errors)

        try:
            metadata = extract_metadata(request.strategy_code)
        except ValueError as e:
            request.errors.add(str(e))
            raise ValidationException(request.errors)

        universe, cadence = metadata.universe, metadata.cadence

        data: pd.DataFrame = await asyncio.to_thread(
            self.data_provider.get_data,
            symbols=universe,
            start_date=request.start_date,
            end_date=request.end_date,
            bar_size=cadence.bar_size,
        )
        if data.empty:
            request.errors.add("No market data available for the specified date range and universe")
            raise ExecutionException(request.errors)

        market_data_json = dataframe_to_json(data, universe)
        return universe, cadence, market_data_json

    async def _run_one(
        self,
        request: BacktestRequest,
        market_data_json: Dict[str, Any],
        cadence: Any,
        params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Optional[BacktestResponse]]:
        """
        Execute a single backtest run with the given resolved params.
        Throttled by _simulation_semaphore. Returns (params, response) or (params, None) on failure.
        """
        async with _simulation_semaphore:
            payload = ExecutionPayload(
                strategy_code=request.strategy_code,
                name=request.name,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                market_data=market_data_json,
                bar_size=cadence.bar_size,
                config_params=params,
            )
            raw = await asyncio.to_thread(self.executor.execute, payload)
            if not raw.errors.is_empty():
                logger.warning(f"Simulation run failed for params {params}: {raw.errors.errors}")
                return params, None
            try:
                validated = self.output_validator.validate(raw)
            except ExecutionException:
                return params, None
            response = build_backtest_response("sim", request, validated, self.data_provider)
            return params, response

    def _get_score(self, response: BacktestResponse, objective: str) -> float:
        fn = OBJECTIVE_FIELDS.get(objective, OBJECTIVE_FIELDS["sharpe"])
        return fn(response.metrics)

    def _build_response(
        self,
        job_id: str,
        sim_type: str,
        runs: List[SimulationRun],
        objective: str,
    ) -> SimulationResponse:
        """Sort runs by objective, surface best params and metrics."""
        obj_fn = OBJECTIVE_FIELDS.get(objective, OBJECTIVE_FIELDS["sharpe"])
        runs.sort(key=lambda sr: obj_fn(sr.result.metrics), reverse=True)
        best = runs[0]
        return SimulationResponse(
            job_id=job_id,
            simulation_type=sim_type,
            best_params=best.config_params,
            best_metrics=best.result.metrics,
            runs=runs,
            total_runs=len(runs),
        )

    @staticmethod
    def _parse_request(request: BacktestRequest) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """
        Split config_params into (sim_type, sim_settings, param_space).
        sim_settings: reserved keys (n_simulations, n_iterations, n_initial, objective)
        param_space:  everything else — the user-defined sweep parameters
        """
        config = request.config_params or {}
        RESERVED = {"simulation", "objective", "n_simulations", "n_iterations", "n_initial"}
        sim_type = config.get("simulation", "")
        sim_settings = {k: config[k] for k in ("objective", "n_simulations", "n_iterations", "n_initial") if k in config}
        param_space = {k: v for k, v in config.items() if k not in RESERVED}
        return sim_type, sim_settings, param_space
