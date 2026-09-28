"""Credential storage for the `hqg` client.

The deployed service sits behind hqg-platform, which authenticates every
proxied request by reading the dashboard's `hqg_auth_token` cookie. A CLI has
no browser cookie jar, so it sends the same token as a cookie of its own and
keeps it in a file the researcher owns.
"""

from __future__ import annotations

import os
from pathlib import Path

COOKIE_NAME = "hqg_auth_token"

CREDENTIALS_PATH = Path.home() / ".hqg" / "credentials"

# Shown wherever a request comes back unauthenticated.
LOGIN_HINT = (
    "Not signed in to the HQG platform.\n"
    "  Copy your token from the dashboard, then run: hqg login"
)


def load_token() -> str | None:
    """Return the researcher's token, or None if they have not signed in.

    HQG_AUTH_TOKEN wins over the file so CI can inject a token without
    writing to the home directory.
    """
    from_env = os.environ.get("HQG_AUTH_TOKEN", "").strip()
    if from_env:
        return from_env

    try:
        stored = CREDENTIALS_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return stored or None


def save_token(token: str) -> Path:
    """Write the token to the credentials file, readable only by its owner."""
    token = token.strip()
    if not token:
        raise ValueError("That token is empty.")

    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Create the file private rather than writing first and chmod-ing after,
    # which would leave the token world-readable in between.
    descriptor = os.open(CREDENTIALS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    # An existing file keeps its old mode through O_CREAT, so set it explicitly.
    os.chmod(CREDENTIALS_PATH, 0o600)
    return CREDENTIALS_PATH


def clear_token() -> bool:
    """Delete the credentials file. Returns False if there was nothing to delete."""
    try:
        CREDENTIALS_PATH.unlink()
    except FileNotFoundError:
        return False
    return True
