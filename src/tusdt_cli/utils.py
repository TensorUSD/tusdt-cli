"""Formatting and output utilities for TUSDT CLI.

Provides balance conversion helpers and Rich-based console output.
"""

import sys
from typing import Any

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


# ---------------------------------------------------------------------------
# Custom Click classes – show full help on missing arguments
# ---------------------------------------------------------------------------

class HelpfulCommand(click.Command):
    """Command that prints full help text when a required argument is missing."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.MissingParameter as e:
            click.echo(ctx.get_help())
            click.echo(f"\nError: {e.format_message()}")
            ctx.exit(2)


class HelpfulGroup(click.Group):
    """Group whose commands show full help on missing arguments."""

    command_class = HelpfulCommand


# ---------------------------------------------------------------------------
# Balance conversion
# ---------------------------------------------------------------------------

def format_balance(raw: int, decimals: int = 12) -> str:
    """Convert a raw on-chain balance to a human-readable decimal string."""
    if raw == 0:
        return "0"
    factor = 10 ** decimals
    whole = raw // factor
    frac = raw % factor
    if frac == 0:
        return str(whole)
    frac_str = str(frac).zfill(decimals).rstrip("0")
    return f"{whole}.{frac_str}"


def parse_balance(human: str, decimals: int = 12) -> int:
    """Convert a human-readable decimal string to a raw on-chain integer."""
    human = human.strip()
    factor = 10 ** decimals
    if "." in human:
        whole_s, frac_s = human.split(".", 1)
        whole = int(whole_s) if whole_s else 0
        frac_s = frac_s[:decimals].ljust(decimals, "0")
        return whole * factor + int(frac_s)
    return int(human) * factor


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def print_table(title: str, columns: list[str], rows: list[list[Any]]) -> None:
    """Render a table with *columns* headers and *rows* data."""
    table = Table(title=title, box=box.ROUNDED, show_lines=True)
    for col in columns:
        table.add_column(col, style="cyan")
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print(table)


def print_dict(title: str, data: dict[str, Any]) -> None:
    """Render key-value pairs inside a bordered panel."""
    text = Text()
    for key, value in data.items():
        text.append(f"  {key}: ", style="bold cyan")
        text.append(f"{value}\n", style="white")
    console.print(Panel(text, title=title, box=box.ROUNDED))


def print_success(msg: str) -> None:
    console.print(f"[bold green]{msg}[/bold green]")


def print_error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")
    sys.exit(1)


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]Warning:[/bold yellow] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


def taostats_url(extrinsic_hash: str, network: str = "finney") -> str:
    """Build a Taostats explorer URL for a given extrinsic hash."""
    return f"https://taostats.io/hash/{extrinsic_hash}?network={network}"


def print_tx_result(result: dict[str, Any], network: str = "finney") -> None:
    """Print transaction result with taostats explorer link."""
    ex_hash = result.get("extrinsic_hash", "")
    url = taostats_url(ex_hash, network)
    print_dict("Transaction", {
        "Extrinsic": ex_hash,
        "Block": result.get("block_hash", ""),
        "Explorer": url,
    })


# ---------------------------------------------------------------------------
# Contract result helpers
# ---------------------------------------------------------------------------

class ContractError(Exception):
    """Raised when a contract call returns an error."""


def unwrap_query(result: Any) -> Any:
    """Unwrap the outer dry-run result and return the inner value.

    The substrate-interface library returns ``contract_result_data`` whose
    ``value_object`` is ``(status, inner)`` where *status* is ``"Ok"`` on
    success.  This helper raises on failure and returns *inner*.
    """
    data = result.contract_result_data.value_object
    if data is None:
        raise ContractError("Empty contract result")
    if data[0] != "Ok":
        err = data[1].value if data[1] is not None else str(data)
        raise ContractError(f"Contract execution failed: {err}")
    return data[1]


def unwrap_option(result: Any) -> Any | None:
    """Unwrap a query that returns ``Option<T>``.

    Returns the inner value (as dict/int/…) or ``None``.
    """
    inner = unwrap_query(result)
    if inner is None:
        return None
    val = inner.value
    if val is None:
        return None
    if isinstance(val, dict) and val.get("None") is not None:
        return None
    return val


def unwrap_result(result: Any) -> Any:
    """Unwrap a query returning ``Result<T, E>`` inside the outer RPC result.

    Returns the ``Ok`` payload or raises ``ContractError`` with the ``Err``
    variant.
    """
    inner = unwrap_query(result)
    val = inner.value
    if isinstance(val, dict):
        if "Ok" in val:
            return val["Ok"]
        if "Err" in val:
            raise ContractError(f"Contract error: {val['Err']}")
    return val


def unwrap_plain(result: Any) -> Any:
    """Unwrap a query returning a plain value (``Balance``, ``u32``, etc.)."""
    inner = unwrap_query(result)
    return inner.value
