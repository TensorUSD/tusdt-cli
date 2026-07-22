"""Bridge session lifecycle.

Manages starting/stopping the bridge daemon, waiting for it to become
reachable, and opening the browser bridge page.

Adapted from btcli's ``bittensor/extension/session.py``.
"""

from __future__ import annotations

import time

from .browser import open_bridge_page
from .client import DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT
from .daemon import start_bridge_daemon, stop_bridge_daemon
from .errors import BridgeError


def bridge_is_reachable(
    host: str = DEFAULT_BRIDGE_HOST,
    port: int = DEFAULT_BRIDGE_PORT,
    timeout: float = 1.0,
) -> bool:
    """Return True if the bridge server is accepting connections."""
    import socket

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


def wait_for_bridge(
    host: str = DEFAULT_BRIDGE_HOST,
    port: int = DEFAULT_BRIDGE_PORT,
    timeout: float = 10.0,
) -> None:
    """Block until the bridge server becomes reachable or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if bridge_is_reachable(host, port):
            return
        time.sleep(0.25)
    raise BridgeError(f"bridge at {host}:{port} did not become reachable within {timeout:.0f}s")


def ensure_bridge(
    browser: str | None = None,
    host: str = DEFAULT_BRIDGE_HOST,
    port: int = DEFAULT_BRIDGE_PORT,
    fresh: bool = False,
) -> None:
    """Ensure the extension bridge is running and the bridge page is open.

    Starts the daemon if not already running (or restarts if *fresh*).
    Opens the bridge page in the browser. Waits for the bridge to be
    reachable before returning.
    """
    if fresh:
        stop_bridge_daemon()
        time.sleep(0.5)

    if not bridge_is_reachable(host, port):
        start_bridge_daemon()
        wait_for_bridge(host, port)
        # Open the bridge HTTP page in the browser.
        http_port = port + 1
        open_bridge_page(f"http://{host}:{http_port}", browser=browser)
        # Give the browser + extension a moment to connect.
        time.sleep(2.0)
    else:
        # Bridge is already running — ensure the page is open.
        http_port = port + 1
        open_bridge_page(f"http://{host}:{http_port}", browser=browser)
