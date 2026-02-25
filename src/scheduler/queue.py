import asyncio

class JobQueue:
    """Async FIFO queue carrying job_id strings only. Can be improved later.
    """
    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def put(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def get(self) -> str:
        return await self._queue.get()

# initialize globally
job_queue = JobQueue()
