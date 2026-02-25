import asyncio
from typing import Optional
from ..models.request import BacktestRequest

class KVStore:
    """Thread-safe async KV store mapping job_id -> BacktestRequest.
    
    Used to fetch and set requests by id (will be used more extensively
    by our scheduler later on.)
    """
    def __init__(self):
        self._store: dict[str, BacktestRequest] = {}
        self._lock = asyncio.Lock()

    async def set(self, job_id: str, request: BacktestRequest) -> None:
        async with self._lock:
            self._store[job_id] = request

    async def get(self, job_id: str) -> Optional[BacktestRequest]:
        async with self._lock:
            return self._store.get(job_id)

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._store.pop(job_id, None)


kv_store = KVStore()
