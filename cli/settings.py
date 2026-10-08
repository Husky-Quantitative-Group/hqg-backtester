"""Client settings to configure hqg client.

Each value can be overridden with an environment variable (e.g. HQG_API_URL);
otherwise the hardcoded default is used.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_API_URL = "https://platform.uconnquant.com/backtester"

HQG_HOME = Path(os.environ.get("HQG_HOME", Path.home() / ".hqg"))


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {value!r}") from None


@dataclass(frozen=True)
class Settings:
    API_URL: str = field(
        default_factory=lambda: os.environ.get("HQG_API_URL", DEFAULT_API_URL).rstrip("/")
    )
    REQUEST_TIMEOUT: float = field(default_factory=lambda: _env_float("HQG_REQUEST_TIMEOUT", 30.0))
    POLL_INTERVAL: float = field(default_factory=lambda: _env_float("HQG_POLL_INTERVAL", 2.0))
    MAX_RETRY_AFTER: float = field(default_factory=lambda: _env_float("HQG_MAX_RETRY_AFTER", 60.0))

settings = Settings()
