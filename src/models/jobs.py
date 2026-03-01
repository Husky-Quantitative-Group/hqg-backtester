from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .response import BacktestResponse


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# TODO: More robust error handling; use our ValidationException & ExecutionException models
# TODO: Implement logging & printing
class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[BacktestResponse] = None
    error: Optional[str] = None
