"""Structured output for the TUSDT CLI.

Provides an ``Output`` class that renders user-facing results through Rich by
default, with opt-in ``--json`` mode for piping and ``--quiet`` mode for
scripting.  All application output flows through this class so modes are applied
consistently without every command having to check flags.

Modeled on btcli's ``cli/output.py``.
"""

from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tusdt_cli.config import EXPLORER_URLS


class Output:
    """Single choke-point for all user-visible rendering.

    Set ``json_mode=True`` to emit machine-readable JSON instead of Rich
    formatting.  Set ``quiet=True`` to suppress non-essential messages.
    """

    def __init__(
        self,
        json_mode: bool = False,
        quiet: bool = False,
        network: str = "finney",
    ) -> None:
        self.json_mode = json_mode
        self.quiet = quiet
        self.network = network
        self._out = Console(highlight=False)
        self._err = Console(stderr=True, highlight=False)

    # ------------------------------------------------------------------
    # Key-value detail
    # ------------------------------------------------------------------

    def detail(self, title: str | None, fields: dict[str, Any]) -> None:
        """Render key-value pairs.

        In JSON mode, emits a flat JSON object.  Otherwise renders a Rich Panel.
        """
        if self.json_mode:
            self._out.print_json(json.dumps(fields))
            return
        text = Text()
        for key, value in fields.items():
            text.append(f"  {key}: ", style="bold cyan")
            text.append(f"{value}\n", style="white")
        self._out.print(Panel(text, title=title, box=box.ROUNDED))

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------

    def table(self, title: str, columns: list[str], rows: list[list[Any]]) -> None:
        """Render a table.

        In JSON mode, emits a JSON array of objects (one per row).
        """
        if self.json_mode:
            self._out.print_json(
                json.dumps([dict(zip(columns, [str(c) for c in row], strict=False)) for row in rows])
            )
            return
        table = Table(title=title, box=box.ROUNDED, show_lines=True)
        for col in columns:
            table.add_column(col, style="cyan")
        for row in rows:
            table.add_row(*[str(c) for c in row])
        self._out.print(table)

    # ------------------------------------------------------------------
    # Transaction result
    # ------------------------------------------------------------------

    def tx_result(self, result: dict[str, Any]) -> None:
        """Render a transaction result with explorer link."""
        ex_hash = result.get("extrinsic_hash", "")
        url = _explorer_url(ex_hash, self.network)
        self.detail(
            "Transaction",
            {
                "Extrinsic": ex_hash,
                "Block": result.get("block_hash", ""),
                "Explorer": url,
            },
        )

    # ------------------------------------------------------------------
    # Status messages
    # ------------------------------------------------------------------

    def success(self, msg: str) -> None:
        """Render a success message (suppressed in quiet mode)."""
        if self.quiet:
            return
        if self.json_mode:
            self._out.print_json(json.dumps({"status": "success", "message": msg}))
            return
        self._out.print(f"[bold green]{msg}[/bold green]")

    def error(
        self,
        msg: str,
        *,
        help: str | None = None,
    ) -> None:
        """Render an error with optional remediation hint.

        In text mode, uses rustc-style ``error: ...`` / ``help: ...`` formatting.
        """
        if self.json_mode:
            payload: dict[str, Any] = {"error": msg}
            if help:
                payload["help"] = help
            self._err.print_json(json.dumps(payload))
            return
        self._err.print(f"[bold red]error:[/bold red] {msg}")
        if help:
            self._err.print(f"[dim]help:[/dim] {help}")

    def warning(self, msg: str) -> None:
        """Render a warning (suppressed in quiet mode)."""
        if self.quiet:
            return
        if self.json_mode:
            self._err.print_json(json.dumps({"warning": msg}))
            return
        self._err.print(f"[bold yellow]warning:[/bold yellow] {msg}")

    def info(self, msg: str) -> None:
        """Render an informational message (suppressed in quiet mode)."""
        if self.quiet:
            return
        if self.json_mode:
            self._err.print_json(json.dumps({"info": msg}))
            return
        self._err.print(f"[dim]{msg}[/dim]")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _explorer_url(extrinsic_hash: str, network: str) -> str:
    """Build an explorer URL for a given extrinsic hash."""
    template = EXPLORER_URLS.get(network)
    if template:
        return template.format(hash=extrinsic_hash)
    # Fallback: ViewPallet
    if network == "finney":
        return f"https://viewpallet.com/explorer/transactions/{extrinsic_hash}"
    return f"https://dev.viewpallet.com/explorer/transactions/{extrinsic_hash}"
