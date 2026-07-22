"""Interactive extension account picker.

Uses Rich to present a list of accounts from the browser extension and lets
the user select one. Filters by address or source when those options are set.

Adapted from btcli's ``bittensor/extension/picker.py``.
"""

from __future__ import annotations


class ExtensionAccount:
    """An account exposed by a browser extension."""

    def __init__(self, address: str, name: str = "", source: str = ""):
        self.address = address
        self.name = name
        self.source = source

    def __repr__(self) -> str:
        parts = [self.address[:12] + "..." + self.address[-6:]]
        if self.name:
            parts.append(self.name)
        if self.source:
            parts.append(f"({self.source})")
        return " ".join(parts)


def pick_extension_account(
    accounts: list[ExtensionAccount],
    *,
    address: str | None = None,
    source: str | None = None,
) -> ExtensionAccount:
    """Select an extension account.

    When *address* is provided, returns the matching account or raises
    ``ValueError``. When *source* is provided, filters to accounts from
    that source. Otherwise, presents an interactive list via Rich.
    """
    if not accounts:
        raise ValueError("no extension accounts available")

    # Filter by source if specified.
    if source:
        filtered = [a for a in accounts if a.source.lower() == source.lower()]
        if not filtered:
            sources = sorted({a.source for a in accounts if a.source})
            raise ValueError(f"no accounts from source {source!r}; available: {sources}")
        accounts = filtered

    # Exact address match.
    if address:
        for a in accounts:
            if a.address == address:
                return a
        raise ValueError(f"account {address!r} not found in extension")

    # Single account — return it directly.
    if len(accounts) == 1:
        return accounts[0]

    # Interactive picker via Rich.
    try:
        from rich.console import Console
        from rich.prompt import Prompt

        console = Console()
        console.print("\n[bold]Available extension accounts:[/bold]\n")
        for i, a in enumerate(accounts, 1):
            console.print(f"  {i}. {a}")
        choice = Prompt.ask(
            "\nSelect an account",
            choices=[str(i) for i in range(1, len(accounts) + 1)],
            default="1",
        )
        return accounts[int(choice) - 1]
    except ImportError:
        return accounts[0]
