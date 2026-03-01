import asyncio
from datetime import datetime, timezone
from typing import Optional

from ..models.jobs import JobRecord, JobStatus
from ..models.response import BacktestResponse


class JobStore:
    """Thread-safe async store mapping job_id → JobRecord.

    Status transitions:
        create        → PENDING
        set_running   → RUNNING    (sets started_at)
        set_completed → COMPLETED  (sets completed_at; record persists for polling)
        set_failed    → FAILED     (sets completed_at; record persists for inspection)
        set_cancelled → evicted    (record removed; only valid from PENDING)
    """

    def __init__(self):
        self._store: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_id: str) -> JobRecord:
        record = JobRecord(
            job_id=job_id,
            status=JobStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            self._store[job_id] = record
        return record

    async def set_running(self, job_id: str) -> None:
        async with self._lock:
            record = self._store.get(job_id)
            if record:
                record.status = JobStatus.RUNNING
                record.started_at = datetime.now(timezone.utc)

    async def set_completed(self, job_id: str, result: BacktestResponse) -> None:
        async with self._lock:
            record = self._store.get(job_id)
            if record:
                record.status = JobStatus.COMPLETED
                record.completed_at = datetime.now(timezone.utc)
                record.result = result

    async def set_failed(self, job_id: str, error: str) -> None:
        async with self._lock:
            record = self._store.get(job_id)
            if record:
                record.status = JobStatus.FAILED
                record.completed_at = datetime.now(timezone.utc)
                record.error = error

    async def set_cancelled(self, job_id: str) -> None:
        async with self._lock:
            self._store.pop(job_id, None)

    async def get(self, job_id: str) -> Optional[JobRecord]:
        async with self._lock:
            return self._store.get(job_id)


job_store = JobStore()
