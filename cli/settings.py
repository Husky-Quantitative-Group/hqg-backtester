"""Client settings, in the same shape as the service's src/config/settings.py.

A stdlib dataclass rather than pydantic-settings, so the client keeps its two
dependencies. Every value is overridable by environment variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# TODO: confirm the externally reachable host and port before release. The
# service listens on 8005, but docker-compose binds it to 127.0.0.1, so the
# VM needs a reverse proxy (or a wider binding) for this URL to resolve.
DEFAULT_API_URL = "http://L1BARCVDAB13OT1.business.uconn.edu:8005"


def _env(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # HQG_API_URL is a development override for pointing at a local service;
    # it is not documented for researchers.
    API_URL: str = field(
        default_factory=lambda: (
            os.environ.get("HQG_API_URL", "").strip() or DEFAULT_API_URL
        ).rstrip("/")
    )

    # One timeout for every HTTP call the client makes.
    REQUEST_TIMEOUT: float = field(default_factory=lambda: _env("HQG_REQUEST_TIMEOUT", 30.0))

    # Status polls count against the service's per-IP rate limit alongside
    # every other request (RATE_LIMIT_PER_MINUTE=60), so polling every second
    # would exhaust a researcher's budget partway through their own backtest.
    POLL_INTERVAL: float = field(default_factory=lambda: _env("HQG_POLL_INTERVAL", 5.0))

    # Cap on a Retry-After the service asks us to wait.
    MAX_RETRY_AFTER: float = field(default_factory=lambda: _env("HQG_MAX_RETRY_AFTER", 60.0))


settings = Settings()
