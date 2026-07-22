"""Open the bridge page in the system browser.

Adapted from btcli's ``bittensor/extension/browser.py``.
"""

from __future__ import annotations

import subprocess
import sys
import webbrowser


def open_bridge_page(url: str, browser: str | None = None) -> None:
    """Open *url* in the specified browser or the system default.

    When *browser* is given, tries to open with that application name
    (e.g. ``"Firefox"``, ``"Google Chrome"``). Falls back to the system
    default if the named browser can't be launched.
    """
    if browser:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", browser, url])
            elif sys.platform == "linux":
                subprocess.Popen([browser, url])
            else:
                subprocess.Popen([browser, url])
            return
        except (FileNotFoundError, OSError):
            pass
    webbrowser.open(url)
