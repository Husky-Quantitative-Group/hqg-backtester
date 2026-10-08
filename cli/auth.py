"""Credential storage & token management for the hqg client."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .settings import HQG_HOME

CREDENTIALS_PATH = HQG_HOME / "credentials"

def load_token() -> str:
    """Fetch saved JWT token from ~/hqg/credentials."""
    try:
        stored = CREDENTIALS_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        print(f"  token at {CREDENTIALS_PATH} cannot be found/read.", file=sys.stderr )
        return None
    return stored


def save_token(token: str) -> Path:
    """Write the token to the credentials file, readable only by its owner."""
    token = token.strip()
    if not token:
        raise ValueError("Provided token is empty.")

    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # open path with configured perms     | write only | make file  | trunc to 0 | rw-------
    descriptor = os.open(CREDENTIALS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")

    # for pre-existing files
    os.chmod(CREDENTIALS_PATH, 0o600)
    return CREDENTIALS_PATH

