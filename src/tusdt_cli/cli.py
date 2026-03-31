"""TUSDT CLI – main entry point.

Registers all command groups and provides config / wallet top-level
commands.
"""

import json
from typing import Optional

import click
from rich.tree import Tree

from tusdt_cli import __version__
from tusdt_cli.config import load_config, save_config, CONFIG_FILE, NETWORKS, apply_network_override
from tusdt_cli.utils import console, print_dict, print_error, print_info, print_success
from tusdt_cli.wallet import get_default_wallet_path, list_wallets

from tusdt_cli.commands.vault import vault_group
from tusdt_cli.commands.token import token_group
from tusdt_cli.commands.auction import auction_group
from tusdt_cli.commands.oracle import oracle_group

_network_option = click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Network preset (overrides rpc & contract addresses)",
)


# ======================================================================
# Root group
# ======================================================================

@click.group()
@click.version_option(__version__, prog_name="tusdt-cli")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """TUSDT CLI – interact with the TUSDT ink! smart-contract system."""
    ctx.ensure_object(dict)


# ======================================================================
# config commands
# ======================================================================

@cli.group("config")
def config_group() -> None:
    """View and update CLI configuration."""


@config_group.command("show")
@_network_option
@click.pass_context
def config_show(ctx: click.Context, network: Optional[str]) -> None:
    """Display the current configuration."""
    cfg = load_config(network=network)
    print_dict("Configuration", cfg)
    print_info(f"Config file: {CONFIG_FILE}")


@config_group.command("set")
@click.option("--network", type=click.Choice(list(NETWORKS.keys()), case_sensitive=False), default=None,
              help="Switch to a network preset (finney, testnet)")
@click.option("--rpc", default=None, help="WebSocket RPC endpoint (e.g. ws://127.0.0.1:9944)")
@click.option("--vault", "vault_address", default=None, help="Vault contract SS58 address")
@click.option("--token", "token_address", default=None, help="Token contract SS58 address")
@click.option("--auction", "auction_address", default=None, help="Auction contract SS58 address")
@click.option("--oracle", "oracle_address", default=None, help="Oracle contract SS58 address")
@click.option("--vault-metadata", default=None, help="Path to tusdt_vault.json ABI")
@click.option("--token-metadata", default=None, help="Path to tusdt_erc20.json ABI")
@click.option("--auction-metadata", default=None, help="Path to tusdt_auction.json ABI")
@click.option("--oracle-metadata", default=None, help="Path to tusdt_oracle.json ABI")
@click.option("--signer", default=None, help="Mnemonic seed phrase or path to keyfile")
@click.option("--wallet-name", default=None, help="Bittensor wallet name to use for signing")
@click.option("--wallet-hotkey", default=None, help="Bittensor hotkey name (default: 'default')")
@click.option("--wallet-path", default=None, help="Path to bittensor wallets directory")
@click.option("--decimals", default=None, type=int, help="Decimal places for balance display")
def config_set(
    network: Optional[str],
    rpc: Optional[str],
    vault_address: Optional[str],
    token_address: Optional[str],
    auction_address: Optional[str],
    oracle_address: Optional[str],
    vault_metadata: Optional[str],
    token_metadata: Optional[str],
    auction_metadata: Optional[str],
    oracle_metadata: Optional[str],
    signer: Optional[str],
    wallet_name: Optional[str],
    wallet_hotkey: Optional[str],
    wallet_path: Optional[str],
    decimals: Optional[int],
) -> None:
    """Update configuration values.  Only provided options are changed."""
    cfg = load_config()
    updates: dict = {}

    # Apply network preset first – individual flags override afterwards
    if network:
        net = network.lower()
        if net in NETWORKS:
            updates.update(NETWORKS[net])
            updates["network"] = net

    pairs = [
        ("rpc", rpc),
        ("vault_address", vault_address),
        ("token_address", token_address),
        ("auction_address", auction_address),
        ("oracle_address", oracle_address),
        ("vault_metadata", vault_metadata),
        ("token_metadata", token_metadata),
        ("auction_metadata", auction_metadata),
        ("oracle_metadata", oracle_metadata),
        ("signer", signer),
        ("wallet_name", wallet_name),
        ("wallet_hotkey", wallet_hotkey),
        ("wallet_path", wallet_path),
        ("decimals", decimals),
    ]
    for key, value in pairs:
        if value is not None:
            updates[key] = value

    if not updates:
        print_info("No options provided – nothing changed.")
        return

    cfg.update(updates)
    save_config(cfg)
    print_success("Configuration updated.")
    for k, v in updates.items():
        console.print(f"  [cyan]{k}[/cyan] = {v}")


# ======================================================================
# wallet commands
# ======================================================================

@cli.group("wallet")
def wallet_group() -> None:
    """List and inspect bittensor wallets."""


@wallet_group.command("list")
@click.option("--path", default=None, help="Custom wallet directory path")
@_network_option
@click.pass_context
def wallet_list(ctx: click.Context, path: Optional[str], network: Optional[str]) -> None:
    """List all bittensor wallets with their addresses."""
    cfg = load_config(network=network)
    wallet_path = path or cfg.get("wallet_path") or str(get_default_wallet_path())

    wallets = list_wallets(wallet_path)
    if not wallets:
        print_info(f"No wallets found in {wallet_path}")
        return

    tree = Tree(f"[bold]Wallets[/bold]  ({wallet_path})")
    for w in wallets:
        addr_display = w.coldkey_address or "[dim]?[/dim]"
        branch = tree.add(f"[bold cyan]{w.name}[/bold cyan]  [dim]coldkey:[/dim] {addr_display}")
        for hk in w.hotkeys:
            hk_addr = hk.ss58_address or ("[dim]<encrypted>[/dim]" if hk.is_encrypted else "[dim]?[/dim]")
            branch.add(f"[green]{hk.name}[/green]  [dim]hotkey:[/dim] {hk_addr}")

    console.print(tree)


# ======================================================================
# Register sub-groups
# ======================================================================

cli.add_command(vault_group)
cli.add_command(token_group)
cli.add_command(auction_group)
cli.add_command(oracle_group)


# ======================================================================
# entry point
# ======================================================================

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
