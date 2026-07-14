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

# Warm import — used by dry_run_result()
from tusdt_cli.utils import format_balance


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
    # Dry-run result
    # ------------------------------------------------------------------

    def dry_run_result(self, result: Any) -> None:
        """Render a dry-run preview (gas, fee, return value)."""
        if self.json_mode:
            payload: dict[str, Any] = {
                "method": result.method,
                "signer": result.signer,
                "gas_required": result.gas_required,
                "gas_consumed": result.gas_consumed,
                "gas_ratio": result.gas_ratio,
                "partial_fee": result.partial_fee,
                "is_success": result.is_success,
            }
            if result.return_value is not None:
                payload["return_value"] = str(result.return_value)
            if result.debug_info:
                payload["debug_info"] = {k: str(v) for k, v in result.debug_info.items()}
            self._out.print_json(json.dumps(payload))
            return

        lines: list[str] = []
        lines.append(f"  Method:       [cyan]{result.method}[/cyan]")
        lines.append(f"  Signer:       [cyan]{result.signer}[/cyan]")

        # Gas
        if result.gas_consumed is not None and result.gas_required is not None:
            gc = _gas_display(result.gas_consumed)
            gr = _gas_display(result.gas_required)
            pct = (result.gas_ratio * 100) if result.gas_ratio else 0
            lines.append(f"  Gas consumed: {gc}  /  required: {gr}  ([yellow]{pct:.1f}%[/yellow])")
        elif result.gas_required is not None:
            lines.append(f"  Gas required: {_gas_display(result.gas_required)}")

        # Fee
        if result.partial_fee is not None:
            lines.append(f"  Est. fee:     [green]{format_balance(result.partial_fee)}[/green]")
        else:
            lines.append("  Est. fee:     [yellow]could not estimate[/yellow]")

        # Status
        if result.is_success:
            lines.append("  Status:       [green]OK[/green]")
            if result.return_value is not None:
                rv = str(result.return_value)
                lines.append(f"  Return:       {rv[:200]}{'...' if len(rv) > 200 else ''}")
        else:
            lines.append("  Status:       [red]FAIL[/red]")
            if result.return_value is not None:
                lines.append(f"  Error:        [red]{result.return_value}[/red]")

        self._out.print(
            Panel("\n".join(lines), title="[dim]dry run[/dim]", box=box.ROUNDED, border_style="dim")
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


def _gas_display(gas: Any) -> str:
    """Human-readable gas value from a WeightV2 dict or scalar."""
    if isinstance(gas, dict):
        ref = gas.get("ref_time", 0)
        proof = gas.get("proof_size", 0)
        return f"ref_time={ref}, proof_size={proof}"
    return str(gas)
