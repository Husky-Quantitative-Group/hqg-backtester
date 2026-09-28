"""Client settings to configure hqg client."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_API_URL = "https://platform.uconnquant.com/backtester"

# Everything the client keeps on disk lives here: credentials and saved runs.
HQG_HOME = Path.home() / ".hqg"

@dataclass(frozen=True)
class Settings:
    API_URL: str = DEFAULT_API_URL.rstrip("/")
    REQUEST_TIMEOUT: float = 30.0
    POLL_INTERVAL: float = 2.0
    MAX_RETRY_AFTER: float = 60.0

settings = Settings()
