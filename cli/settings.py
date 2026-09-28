"""Client settings, in the same shape as the service's src/config/settings.py.

A stdlib dataclass rather than pydantic-settings, so the client keeps its two
dependencies. Every value is overridable by environment variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Researchers reach the backtester through hqg-platform, which proxies
# /backtester/* to the service and strips the prefix. The backtester container
# is never exposed directly: it binds 127.0.0.1 on the VM and is reachable only
# from the shared `hqg_network` as http://hqg-backtester:8005.
DEFAULT_API_URL = "https://platform.uconnquant.com/backtester"


def _env(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # HQG_API_URL points the client somewhere other than the deployed platform,
    # typically a local `docker compose up` on http://localhost:8005.
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
