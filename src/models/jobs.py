from enum import Enum
from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel

from .response import BacktestResponse
from .simulation import SimulationResponse


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# TODO: More robust error handling; use our ValidationException & ExecutionException models
class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Union[BacktestResponse, SimulationResponse]] = None
    error: Optional[str] = None
    logs: list[str] = []
