from typing import Dict, Any, List
from pydantic import BaseModel

from .response import BacktestResponse, PerformanceMetrics


class SimulationRun(BaseModel):
    config_params: Dict[str, Any]
    result: BacktestResponse


class SimulationResponse(BaseModel):
    job_id: str
    simulation_type: str
    best_params: Dict[str, Any]
    best_metrics: PerformanceMetrics
    runs: List[SimulationRun]
    total_runs: int
