"""Auth token persistence for the extension bridge client.

The bridge server generates a random bearer token on startup and writes it
to ``~/.tusdt-cli/extension_bridge.token``. The Python client reads it from
the same path to authenticate its WebSocket connection.
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path


def _token_dir() -> Path:
    return Path.home() / ".tusdt-cli"


def _token_path() -> Path:
    return _token_dir() / "extension_bridge.token"


def write_bridge_token() -> str:
    """Generate a fresh token and write it to the token file. Returns the token."""
    d = _token_dir()
    d.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    path = _token_path()
    # Restrict permissions before writing the secret.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, token.encode())
    finally:
        os.close(fd)
    return token


def read_bridge_token() -> str | None:
    """Read the current bridge auth token, or None if no token exists."""
    path = _token_path()
    if not path.exists():
        return None
    try:
        return path.read_text().strip()
    except OSError:
        return None


def clear_bridge_token() -> None:
    """Remove the token file."""
    path = _token_path()
    if path.exists():
        path.unlink()
