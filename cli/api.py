"""HTTP client for the hosted backtesting service."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

# TODO: replace with the real School of Business VM hostname before release.
DEFAULT_API_URL = "http://hqg-vm.business.uconn.edu:8005"

# HQG_API_URL is a development override for pointing at a local service; it is
# not documented for researchers.
API_URL = (os.environ.get("HQG_API_URL", "").strip() or DEFAULT_API_URL).rstrip("/")

HEALTH_TIMEOUT = 3.0
SUBMIT_TIMEOUT = 30.0
POLL_TIMEOUT = 15.0

# Status polls count against the service's per-IP rate limit alongside every
# other request (RATE_LIMIT_PER_MINUTE=60), so polling every second would
# exhaust a researcher's budget partway through their own backtest. Poll
# quickly only for the first few seconds, then settle down.
FAST_POLL_INTERVAL = 2.0
SLOW_POLL_INTERVAL = 5.0
FAST_POLL_WINDOW = 10.0

MAX_RETRY_AFTER = 60.0


def _retry_after(response: httpx.Response) -> float:
    try:
        return float(response.headers.get("Retry-After", 60))
    except (TypeError, ValueError):
        return 60.0


class BacktestClient:
    """Thin wrapper over the service's job API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client()

    def health(self) -> None:
        """Confirm the service is reachable."""
        try:
            response = self._http.get(f"{self.base_url}/health", timeout=HEALTH_TIMEOUT)
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach the backtesting service at {self.base_url}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"Health check returned HTTP {response.status_code}"
            )

    def submit(self, payload: dict[str, Any]) -> str:
        """Enqueue a backtest and return its job id."""
        try:
            response = self._http.post(
                f"{self.base_url}/api/v1/backtest", json=payload, timeout=SUBMIT_TIMEOUT
            )
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach the backtesting service at {self.base_url}: {exc}"
            ) from exc

        if response.status_code == 429:
            raise RuntimeError(
                "The service is rate limiting this machine.\n"
                f"Try again in {_retry_after(response):.0f}s."
            )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text.strip()}")

        job_id = response.json().get("job_id")
        if not job_id:
            raise RuntimeError("The service accepted the job but returned no job id.")
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return the job record, or None if the service has no such job."""
        while True:
            try:
                response = self._http.get(
                    f"{self.base_url}/api/v1/backtest/{job_id}", timeout=POLL_TIMEOUT
                )
            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"Could not reach the backtesting service at {self.base_url}: {exc}"
                ) from exc

            if response.status_code == 429:
                # Polls share the per-IP rate limit; wait it out and try again.
                time.sleep(min(_retry_after(response), MAX_RETRY_AFTER))
                continue
            if response.status_code == 404:
                return None
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text.strip()}")
            return response.json()

    def cancel(self, job_id: str) -> str:
        """Ask the service to cancel a job. Returns a description of what happened."""
        try:
            response = self._http.delete(
                f"{self.base_url}/api/v1/backtest/{job_id}", timeout=POLL_TIMEOUT
            )
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach the backtesting service at {self.base_url}: {exc}"
            ) from exc

        if response.status_code == 200:
            return "cancelled"
        if response.status_code == 404:
            return "no longer exists"
        if response.status_code == 409:
            # Only PENDING jobs can be cancelled; it is already running or finished.
            return "already started, so it will run to completion"
        return f"could not be cancelled (HTTP {response.status_code})"

    def wait_for_result(
        self,
        job_id: str,
        timeout: float,
        on_status: Callable[[str], None] = lambda status: None,
    ) -> dict[str, Any]:
        """Poll until the job reaches a terminal state, reporting status changes."""
        started = time.monotonic()
        deadline = started + timeout
        last_status: str | None = None

        while True:
            record = self.get_job(job_id)
            if record is None:
                raise RuntimeError(
                    f"Job {job_id} no longer exists.\n"
                    "The service keeps job state in memory; it may have restarted."
                )

            status = record.get("status", "UNKNOWN")
            if status != last_status:
                last_status = status
                on_status(status)

            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                return record

            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Gave up waiting after {timeout:.0f}s; the job is still {status}.\n"
                    f"It may still finish. Check with: hqg status {job_id}"
                )

            elapsed = time.monotonic() - started
            interval = FAST_POLL_INTERVAL if elapsed < FAST_POLL_WINDOW else SLOW_POLL_INTERVAL
            time.sleep(min(interval, max(deadline - time.monotonic(), 0.0)))
