"""TUSDT CLI – main entry point.

Registers all command groups and provides config / wallet top-level
commands.
"""

import json

import click
from rich.tree import Tree

from tusdt_cli import __version__
from tusdt_cli.commands.auction import auction_group
from tusdt_cli.commands.election import election_group
from tusdt_cli.commands.governance import governance_group
from tusdt_cli.commands.lending import lending_group
from tusdt_cli.commands.oracle import oracle_group
from tusdt_cli.commands.token import token_group
from tusdt_cli.commands.treasury import treasury_group
from tusdt_cli.commands.vault import vault_group
from tusdt_cli.config import CONFIG_FILE, NETWORKS, load_config, save_config
from tusdt_cli.context import CLIContext
from tusdt_cli.globals import (
    dry_run_option,
    extension_browser_option,
    extension_source_option,
    json_option,
    ledger_account_option,
    ledger_index_option,
    ledger_option,
    network_option,
    quiet_option,
    signer_address_option,
    signer_backend_option,
    verbose_option,
    yes_option,
)
from tusdt_cli.utils import HelpfulGroup, console, print_dict, print_info, print_success
from tusdt_cli.wallet import get_default_wallet_path, list_wallets, resolve_signer_address

# ======================================================================
# Root group
# ======================================================================


@click.group()
@click.version_option(__version__, prog_name="tusdt-cli")
@json_option
@quiet_option
@verbose_option
@dry_run_option
@yes_option
@signer_backend_option
@signer_address_option
@extension_source_option
@extension_browser_option
@ledger_option
@ledger_account_option
@ledger_index_option
@click.pass_context
def cli(
    ctx: click.Context,
    use_json: bool = False,
    quiet: bool = False,
    verbosity: int = 0,
    dry_run: bool = False,
    assume_yes: bool = False,
    signer_backend: str | None = None,
    signer_address: str | None = None,
    extension_source: str | None = None,
    extension_browser: str | None = None,
    ledger: bool = False,
    ledger_account: int = 0,
    ledger_index: int = 0,
) -> None:
    """TUSDT CLI – interact with the TUSDT ink! smart-contract system."""
    # --ledger is shorthand for --signer-backend ledger (mirrors btcli pattern)
    backend = signer_backend
    if ledger:
        backend = "ledger"
    # Read the saved network from config so state.network reflects the
    # user's saved preference, not the hardcoded default.
    from tusdt_cli.config import load_config as _load_config

    saved_network = _load_config().get("network", "finney")

    ctx.obj = CLIContext(
        use_json=use_json,
        quiet=quiet,
        assume_yes=assume_yes,
        verbosity=verbosity,
        dry_run=dry_run,
        signer_backend=backend,
        signer_address=signer_address,
        extension_source=extension_source,
        extension_browser=extension_browser,
        ledger_account=ledger_account,
        ledger_index=ledger_index,
        network=saved_network,
    )


# ======================================================================
# config commands
# ======================================================================


@cli.group("config", cls=HelpfulGroup)
def config_group() -> None:
    """View and update CLI configuration."""


@config_group.command("show")
@network_option
@click.pass_context
def config_show(ctx: click.Context, network: str | None) -> None:
    """Display the current configuration.

    Sensitive values (mnemonic seed phrases) are never shown — the
    derived SS58 address is displayed instead.
    """
    cfg = load_config(network=network)
    display = dict(cfg)

    # Mask the raw signer mnemonic / path — show the derived address instead.
    if display.get("signer"):
        addr = resolve_signer_address(cfg)
        if addr:
            display["signer_address"] = addr
            display["signer"] = "(hidden — use 'tusdt config show --verbose' to view path)"
        else:
            display["signer"] = "(encrypted keyfile)"

    print_dict("Configuration", display)
    print_info(f"Config file: {CONFIG_FILE}")


@config_group.command("set")
@click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Switch to a network preset (finney, testnet)",
)
@click.option("--rpc", default=None, help="WebSocket RPC endpoint (e.g. ws://127.0.0.1:9944)")
@click.option("--vault", "vault_address", default=None, help="Vault contract SS58 address")
@click.option("--token", "token_address", default=None, help="Token contract SS58 address")
@click.option("--auction", "auction_address", default=None, help="Auction contract SS58 address")
@click.option("--oracle", "oracle_address", default=None, help="Oracle contract SS58 address")
@click.option("--governance", "governance_address", default=None, help="Governance contract SS58 address")
@click.option("--treasury", "treasury_address", default=None, help="Treasury contract SS58 address")
@click.option("--election", "election_address", default=None, help="Election contract SS58 address")
@click.option("--lending", "lending_address", default=None, help="Lending pool contract SS58 address")
@click.option("--vault-metadata", default=None, help="Path to tusdt_vault.json ABI")
@click.option("--token-metadata", default=None, help="Path to tusdt_erc20.json ABI")
@click.option("--auction-metadata", default=None, help="Path to tusdt_auction.json ABI")
@click.option("--oracle-metadata", default=None, help="Path to tusdt_oracle.json ABI")
@click.option("--governance-metadata", default=None, help="Path to tusdt_governance.json ABI")
@click.option("--treasury-metadata", default=None, help="Path to tusdt_treasury.json ABI")
@click.option("--election-metadata", default=None, help="Path to tusdt_election.json ABI")
@click.option("--lending-metadata", default=None, help="Path to tusdt_lending_pool.json ABI")
@click.option("--signer", default=None, help="Mnemonic seed phrase or path to keyfile")
@click.option("--wallet-name", default=None, help="Bittensor wallet name to use for signing")
@click.option("--wallet-hotkey", default=None, help="Bittensor hotkey name (default: 'default')")
@click.option("--wallet-path", default=None, help="Path to bittensor wallets directory")
@click.option("--decimals", default=None, type=int, help="Decimal places for balance display")
def config_set(
    network: str | None,
    rpc: str | None,
    vault_address: str | None,
    token_address: str | None,
    auction_address: str | None,
    oracle_address: str | None,
    governance_address: str | None,
    treasury_address: str | None,
    election_address: str | None,
    lending_address: str | None,
    vault_metadata: str | None,
    token_metadata: str | None,
    auction_metadata: str | None,
    oracle_metadata: str | None,
    governance_metadata: str | None,
    treasury_metadata: str | None,
    election_metadata: str | None,
    lending_metadata: str | None,
    signer: str | None,
    wallet_name: str | None,
    wallet_hotkey: str | None,
    wallet_path: str | None,
    decimals: int | None,
) -> None:
    """Update configuration values.  Only provided options are changed."""
    # Read only the raw saved overrides — not the full resolved config.
    # This prevents baking in package-default ABI paths or network-preset
    # addresses, so package upgrades automatically pick up new defaults.
    saved_overrides: dict = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved_overrides = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    updates: dict = {}

    # When --network is passed, save only the network name.
    # load_config() resolves preset addresses dynamically on every call, so
    # persisting them would prevent new package defaults from being picked up.
    if network:
        net = network.lower()
        if net in NETWORKS:
            updates["network"] = net
            # Clear any previously baked-in network keys from the saved file
            # so upgraded package defaults take effect (migration of old configs).
            for key in (
                "rpc",
                "vault_address",
                "token_address",
                "auction_address",
                "oracle_address",
                "governance_address",
                "treasury_address",
                "election_address",
                "lending_address",
            ):
                saved_overrides.pop(key, None)
            for key in (
                "vault_metadata",
                "token_metadata",
                "auction_metadata",
                "oracle_metadata",
                "governance_metadata",
                "treasury_metadata",
                "election_metadata",
                "lending_metadata",
            ):
                saved_overrides.pop(key, None)

    pairs = [
        ("rpc", rpc),
        ("vault_address", vault_address),
        ("token_address", token_address),
        ("auction_address", auction_address),
        ("oracle_address", oracle_address),
        ("governance_address", governance_address),
        ("treasury_address", treasury_address),
        ("election_address", election_address),
        ("lending_address", lending_address),
        ("vault_metadata", vault_metadata),
        ("token_metadata", token_metadata),
        ("auction_metadata", auction_metadata),
        ("oracle_metadata", oracle_metadata),
        ("governance_metadata", governance_metadata),
        ("treasury_metadata", treasury_metadata),
        ("election_metadata", election_metadata),
        ("lending_metadata", lending_metadata),
        ("signer", signer),
        ("wallet_name", wallet_name),
        ("wallet_hotkey", wallet_hotkey),
        ("wallet_path", wallet_path),
        ("decimals", decimals),
    ]
    for key, value in pairs:
        if value is not None:
            updates[key] = value

    # Derive and persist the signer SS58 address for safe display.
    if updates.get("signer") or updates.get("wallet_name"):
        # Build a temporary config with the new values merged in so that
        # resolve_signer_address sees the fresh state.
        temp = dict(saved_overrides)
        temp.update(updates)
        addr = resolve_signer_address(temp)
        if addr:
            updates["signer_address"] = addr

    if not updates:
        print_info("No options provided – nothing changed.")
        return

    saved_overrides.update(updates)
    save_config(saved_overrides)
    print_success("Configuration updated.")
    for k, v in updates.items():
        console.print(f"  [cyan]{k}[/cyan] = {v}")


# ======================================================================
# wallet commands
# ======================================================================


@cli.group("wallet", cls=HelpfulGroup)
def wallet_group() -> None:
    """List and inspect bittensor wallets."""


@wallet_group.command("list")
@click.option("--path", default=None, help="Custom wallet directory path")
@network_option
@click.pass_context
def wallet_list(ctx: click.Context, path: str | None, network: str | None) -> None:
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
cli.add_command(governance_group)
cli.add_command(lending_group)
cli.add_command(treasury_group)
cli.add_command(election_group)


# ======================================================================
# shell completions
# ======================================================================


@cli.group("completion", cls=HelpfulGroup, hidden=True)
def completion_group() -> None:
    """Generate shell completion scripts for bash, zsh, or fish."""


@completion_group.command("bash")
def completion_bash() -> None:
    """Print bash completion script (source it from ~/.bashrc)."""
    prog = "tusdt"
    script = f"""\
# {prog} completion for bash – add this to ~/.bashrc or source it
eval "$(_{prog.upper()}_COMPLETE=bash_source {prog})"
"""
    console.print(script.strip())


@completion_group.command("zsh")
def completion_zsh() -> None:
    """Print zsh completion script (source it from ~/.zshrc)."""
    prog = "tusdt"
    script = f"""\
# {prog} completion for zsh – add this to ~/.zshrc or source it
eval "$(_{prog.upper()}_COMPLETE=zsh_source {prog})"
"""
    console.print(script.strip())


@completion_group.command("fish")
def completion_fish() -> None:
    """Print fish completion script (source it from ~/.config/fish/completions/)."""
    prog = "tusdt"
    script = f"""\
# {prog} completion for fish
eval (env _{prog.upper()}_COMPLETE=fish_source {prog})
"""
    console.print(script.strip())


# ======================================================================
# ======================================================================
# extension commands — browser extension bridge management
# ======================================================================


@cli.group("extension", cls=HelpfulGroup)
def extension_group() -> None:
    """Manage the browser extension bridge for signing."""


@extension_group.command("start")
@click.option("--browser", type=str, default=None, help="Browser to open the bridge page in")
def extension_start(browser: str | None) -> None:
    """Start the extension bridge daemon and open the bridge page."""
    from tusdt_cli.extension import ensure_bridge

    print_info("Starting extension bridge...")
    ensure_bridge(browser=browser, fresh=True)
    print_success("Extension bridge started! A browser tab should have opened.")
    print_info("Run 'tusdt --signer-backend extension <command>' to sign via the extension.")


@extension_group.command("stop")
def extension_stop() -> None:
    """Stop the extension bridge daemon."""
    from tusdt_cli.extension import stop_bridge_daemon

    stop_bridge_daemon()
    print_success("Extension bridge stopped.")


@extension_group.command("status")
def extension_status() -> None:
    """Check if the extension bridge is running."""
    from tusdt_cli.extension.session import bridge_is_reachable

    if bridge_is_reachable():
        print_success("Extension bridge is running on ws://127.0.0.1:39295")
    else:
        print_info("Extension bridge is not running.")


# ======================================================================
# entry point
# ======================================================================


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
