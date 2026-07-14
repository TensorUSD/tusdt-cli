"""Shared Click options, defined once and reused across all command files.

Modeled on btcli's ``cli/globals.py`` pattern — every command file imports
these instead of redeclaring ``--network`` and ``--wallet-name`` locally.
"""

from __future__ import annotations

import click

from tusdt_cli.config import NETWORKS

network_option = click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Network preset (overrides rpc & contract addresses)",
)

wallet_option = click.option(
    "--wallet-name",
    default=None,
    help="Bittensor wallet name for signing (prompts for coldkey password)",
)

json_option = click.option(
    "--json",
    "use_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON instead of formatted text",
)

quiet_option = click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress non-essential output",
)

yes_option = click.option(
    "--yes",
    "-y",
    "assume_yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts (assume yes)",
)

verbose_option = click.option(
    "-v",
    "verbosity",
    count=True,
    help="Increase diagnostic logging (-v for INFO, -vv for DEBUG)",
)
