"""CLI logging configuration.

The library emits diagnostics through stdlib loggers under ``tusdt_cli.*`` and
never configures handlers itself (library convention). The CLI is the
application, so this module wires those loggers to a Rich handler on stderr —
exactly once, at entry — keeping stdout pure data for ``--json`` piping.

Verbosity ladder (the ``-v`` flag counts):

    --quiet   ERROR       only unrecoverable problems
    (default) WARNING     degraded-but-continuing conditions
    -v        INFO        connection lifecycle, endpoint fallback, retries
    -vv       DEBUG       full chain-communication diagnostics

``TUSDT_LOG`` (error/warning/info/debug) overrides the flags, which is handy
for CI runs and bug reports where editing the command line is awkward.

User-facing results, prompts, and errors are NOT logging — they go through
``output.Output``. Logging is diagnostics only.
"""

from __future__ import annotations

import logging
import os

from rich.console import Console
from rich.logging import RichHandler

LOGGER_NAME = "tusdt_cli"
ENV_VAR = "TUSDT_LOG"

# Env value -> (verbosity, quiet), mirroring the flag ladder.
_ENV_LEVELS: dict[str, tuple[int, bool]] = {
    "error": (0, True),
    "warning": (0, False),
    "info": (1, False),
    "debug": (2, False),
}


def setup_logging(verbosity: int = 0, quiet: bool = False) -> None:
    """Configure diagnostic logging for the CLI process.

    Safe to call again — the previous handler is replaced rather than stacked.
    """
    env = os.environ.get(ENV_VAR, "").strip().lower()
    if env in _ENV_LEVELS:
        verbosity, quiet = _ENV_LEVELS[env]

    if verbosity <= 0:
        level = logging.ERROR if quiet else logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    handler = RichHandler(
        console=Console(stderr=True),
        show_time=False,
        show_path=verbosity >= 2,
        rich_tracebacks=verbosity >= 2,
    )

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    _replace_handler(logger, handler)


def _replace_handler(target: logging.Logger, handler: logging.Handler) -> None:
    _remove_our_handlers(target)
    handler.set_name("tusdt-cli")
    target.addHandler(handler)


def _remove_our_handlers(target: logging.Logger) -> None:
    for existing in list(target.handlers):
        if existing.get_name() == "tusdt-cli":
            target.removeHandler(existing)
