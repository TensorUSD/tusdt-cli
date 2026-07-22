"""Background daemon that runs the extension bridge server.

Starts a child process that runs the bridge WebSocket server. The PID is
written to ``~/.tusdt-cli/extension_bridge.pid`` so ``stop_bridge_daemon``
can send SIGTERM.

Adapted from btcli's ``bittensor/extension/daemon.py``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


def _pid_path() -> Path:
    d = Path.home() / ".tusdt-cli"
    d.mkdir(parents=True, exist_ok=True)
    return d / "extension_bridge.pid"


def start_bridge_daemon() -> int:
    """Start the bridge server as a background child process.

    Returns the PID of the child process.
    """
    script = Path(__file__).resolve().parent / "bridge.py"
    proc = subprocess.Popen(
        [sys.executable, str(script), "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    _pid_path().write_text(str(proc.pid))
    return proc.pid


def stop_bridge_daemon() -> None:
    """Stop a running bridge daemon by sending SIGTERM to the PID on file."""
    path = _pid_path()
    if not path.exists():
        return
    try:
        pid = int(path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, ValueError, OSError):
        pass
    finally:
        if path.exists():
            path.unlink()
