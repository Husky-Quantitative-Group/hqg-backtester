import logging
from contextvars import ContextVar

current_job_id: ContextVar[str | None] = ContextVar("current_job_id", default=None)


class LogHandler(logging.Handler):
    """Captures log records per job via ContextVar and appends them to JobStore.

    Each asyncio task (and threads it spawns) inherits its own copy of
    current_job_id, so concurrent jobs never bleed into each other's log buckets.
    emit() calls job_store.append_log synchronously, making it safe from any
    thread including thread pool executors.
    """

    def __init__(self, job_store):
        super().__init__()
        self._job_store = job_store

    def emit(self, record: logging.LogRecord) -> None:
        job_id = current_job_id.get()
        if job_id is None:
            return
        self._job_store.append_log(job_id, self.format(record))
