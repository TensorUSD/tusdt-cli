"""Treasury CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import NETWORKS, load_config
from tusdt_cli.utils import (
    ModeAwareGroup,
    format_balance,
    parse_balance,
    print_dict,
    print_error,
    print_info,
    print_success,
    print_tx_result,
)
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair

_network_option = click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Network preset (overrides rpc & contract addresses)",
)

_wallet_option = click.option(
    "--wallet-name",
    default=None,
    help="Bittensor wallet name for signing (prompts for coldkey password)",
)

_TREASURY_ADVANCED = {"set-governance", "distribute", "release"}

_FUND_CHOICE = click.Choice(
    ["emergency", "operation", "insurance", "dividend", "buyback", "voting"],
    case_sensitive=False,
)

_TOKEN_KIND_CHOICE = click.Choice(["tusdt", "native"], case_sensitive=False)


@click.group("treasury", cls=ModeAwareGroup, advanced_commands=_TREASURY_ADVANCED)
def treasury_group() -> None:
    """Treasury operations for the TUSDT system."""


# ======================================================================
# Basic (read) commands
# ======================================================================

# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@treasury_group.command("governance")
@_network_option
@click.pass_context
def treasury_governance(ctx: click.Context, network: str | None) -> None:
    """Show the governance address registered in the treasury contract.

    \b
    Examples:
      tusdt treasury governance
      tusdt treasury governance --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.treasury_get_governance(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Treasury Governance", {"Address": addr})


# ------------------------------------------------------------------
# token
# ------------------------------------------------------------------


@treasury_group.command("token")
@_network_option
@click.pass_context
def treasury_token(ctx: click.Context, network: str | None) -> None:
    """Show the TUSDT token address registered in the treasury contract.

    \b
    Examples:
      tusdt treasury token
      tusdt treasury token --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.treasury_get_token(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Treasury Token", {"Address": addr})


# ------------------------------------------------------------------
# fund-balance-tusdt
# ------------------------------------------------------------------


@treasury_group.command("fund-balance-tusdt")
@click.argument("fund", type=_FUND_CHOICE, metavar="<fund>")
@_network_option
@click.pass_context
def fund_balance_tusdt(ctx: click.Context, fund: str, network: str | None) -> None:
    """Show the TUSDT balance for a specific fund.

    \b
    FUND is one of: emergency, operation, insurance, dividend, buyback, voting.
    Examples:
      tusdt treasury fund-balance-tusdt emergency
      tusdt treasury fund-balance-tusdt insurance --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        fund_dict = {fund.capitalize(): None}
        balance = client.treasury_fund_balance_tusdt(keypair, fund_dict)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        f"Fund Balance – {fund.capitalize()} (TUSDT)",
        {
            "Fund": fund.capitalize(),
            "Balance": format_balance(balance, decimals),
            "Raw": balance,
        },
    )


# ------------------------------------------------------------------
# fund-balance-native
# ------------------------------------------------------------------


@treasury_group.command("fund-balance-native")
@click.argument("fund", type=_FUND_CHOICE, metavar="<fund>")
@_network_option
@click.pass_context
def fund_balance_native(ctx: click.Context, fund: str, network: str | None) -> None:
    """Show the native balance for a specific fund.

    \b
    FUND is one of: emergency, operation, insurance, dividend, buyback, voting.
    Examples:
      tusdt treasury fund-balance-native emergency
      tusdt treasury fund-balance-native insurance --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        fund_dict = {fund.capitalize(): None}
        balance = client.treasury_fund_balance_native(keypair, fund_dict)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        f"Fund Balance – {fund.capitalize()} (Native)",
        {
            "Fund": fund.capitalize(),
            "Balance": format_balance(balance, decimals),
            "Raw": balance,
        },
    )


# ------------------------------------------------------------------
# pending-tusdt
# ------------------------------------------------------------------


@treasury_group.command("pending-tusdt")
@_network_option
@click.pass_context
def pending_tusdt(ctx: click.Context, network: str | None) -> None:
    """Show the total pending TUSDT balance awaiting distribution.

    \b
    Examples:
      tusdt treasury pending-tusdt
      tusdt treasury pending-tusdt --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        balance = client.treasury_pending_tusdt(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        "Pending TUSDT",
        {
            "Balance": format_balance(balance, decimals),
            "Raw": balance,
        },
    )


# ------------------------------------------------------------------
# pending-native
# ------------------------------------------------------------------


@treasury_group.command("pending-native")
@_network_option
@click.pass_context
def pending_native(ctx: click.Context, network: str | None) -> None:
    """Show the total pending native balance awaiting distribution.

    \b
    Examples:
      tusdt treasury pending-native
      tusdt treasury pending-native --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        balance = client.treasury_pending_native(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict(
        "Pending Native",
        {
            "Balance": format_balance(balance, decimals),
            "Raw": balance,
        },
    )


# ======================================================================
# Advanced (write) commands
# ======================================================================

# ------------------------------------------------------------------
# set-governance
# ------------------------------------------------------------------


@treasury_group.command("set-governance")
@click.argument("address", type=str, metavar="<ss58-address>")
@_wallet_option
@_network_option
@click.pass_context
def treasury_set_governance_cmd(
    ctx: click.Context,
    address: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Set a new governance address for the treasury (governance only).

    \b
    ADDRESS is the SS58 address of the new governance account.
    Examples:
      tusdt treasury set-governance 5GrwvaEF... --wallet-name MyWallet
      tusdt treasury set-governance 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Setting treasury governance to {address}...")

    try:
        client = TUSDTClient(config)
        result = client.treasury_set_governance(keypair, address)
        print_success("Treasury governance updated!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# distribute
# ------------------------------------------------------------------


@treasury_group.command("distribute")
@_wallet_option
@_network_option
@click.pass_context
def treasury_distribute_cmd(
    ctx: click.Context,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Distribute pending TUSDT and native funds to their respective fund balances.

    \b
    Examples:
      tusdt treasury distribute --wallet-name MyWallet
      tusdt treasury distribute --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info("Distributing pending funds to fund balances...")

    try:
        client = TUSDTClient(config)
        result = client.treasury_distribute(keypair)
        print_success("Funds distributed!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# release
# ------------------------------------------------------------------


@treasury_group.command("release")
@click.argument("fund", type=_FUND_CHOICE, metavar="<fund>")
@click.option("--token-kind", type=_TOKEN_KIND_CHOICE, required=True, help="Token kind: tusdt or native")
@click.option(
    "--amount", type=str, required=True, help="Amount to release in human-readable units (e.g. 1000.0)"
)
@click.option(
    "--recipient",
    type=str,
    required=True,
    metavar="<ss58-address>",
    help="Recipient SS58 address (e.g. 5GrwvaEF...)",
)
@_wallet_option
@_network_option
@click.pass_context
def treasury_release_cmd(
    ctx: click.Context,
    fund: str,
    token_kind: str,
    amount: str,
    recipient: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Release funds from a specific fund to a recipient (governance only).

    \b
    FUND is one of: emergency, operation, insurance, dividend, buyback, voting.
    Examples:
      tusdt treasury release emergency --token-kind tusdt --amount 5000 --recipient 5GrwvaEF... --wallet-name MyWallet
      tusdt treasury release insurance --token-kind native --amount 10 --recipient 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    # Build Fund and TokenKind dicts
    fund_dict = {fund.capitalize(): None}
    token_kind_dict = {"Tusdt": None} if token_kind.lower() == "tusdt" else {"Native": None}

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Releasing {amount} {token_kind.upper()} from {fund} fund to {recipient}...")

    try:
        client = TUSDTClient(config)
        result = client.treasury_release(keypair, fund_dict, token_kind_dict, raw_amount, recipient)
        print_success("Funds released!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
