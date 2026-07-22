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

dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview the transaction without submitting (gas + fee estimate)",
)

signer_backend_option = click.option(
    "--signer-backend",
    type=click.Choice(["wallet", "ledger", "extension"], case_sensitive=False),
    default=None,
    help="Signing backend: wallet (default), ledger, or extension",
)

ledger_option = click.option(
    "--ledger",
    is_flag=True,
    default=False,
    help="Use Ledger hardware wallet (shorthand for --signer-backend ledger)",
)

ledger_account_option = click.option(
    "--ledger-account",
    type=int,
    default=0,
    help="Ledger derivation account (m/44'/354'/ACCOUNT'/0'/index). Default 0.",
)

ledger_index_option = click.option(
    "--ledger-index",
    type=int,
    default=0,
    help="Ledger derivation address index (m/44'/354'/account'/0'/INDEX). Default 0.",
)

# -- extension signing options (matches btcli's pattern) -----------------------

extension_source_option = click.option(
    "--extension-source",
    type=str,
    default=None,
    help="Filter extension accounts by source (e.g. polkadot-js, talisman)",
)

extension_browser_option = click.option(
    "--extension-browser",
    type=str,
    default=None,
    help="Browser to open the bridge page in (e.g. Firefox, 'Google Chrome')",
)

signer_address_option = click.option(
    "--signer-address",
    type=str,
    default=None,
    help="Specific extension account address to use (skips interactive picker)",
)
