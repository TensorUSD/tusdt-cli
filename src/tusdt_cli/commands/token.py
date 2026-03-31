"""Token (ERC-20) CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import load_config, NETWORKS
from tusdt_cli.utils import (
    ContractError,
    format_balance,
    parse_balance,
    print_dict,
    print_error,
    print_info,
    print_success,
    print_tx_result,
)
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair, resolve_ss58

_network_option = click.option(
    "--network",
    type=click.Choice(list(NETWORKS.keys()), case_sensitive=False),
    default=None,
    help="Network preset (overrides rpc & contract addresses)",
)

_wallet_option = click.option(
    "--wallet-name", default=None,
    help="Bittensor wallet name for signing (prompts for coldkey password)",
)


@click.group("token")
def token_group() -> None:
    """TUSDT token operations."""


# ------------------------------------------------------------------
# balance
# ------------------------------------------------------------------

@token_group.command("balance")
@click.argument("account", required=False, default=None)
@_wallet_option
@_network_option
@click.pass_context
def balance(ctx: click.Context, account: str | None, wallet_name: str | None, network: str | None) -> None:
    """Show the TUSDT token balance for an account.

    ACCOUNT can be an SS58 address or a bittensor wallet name.
    If omitted, --wallet-name is used to resolve the address.
    """
    config = load_config(network=network or ctx.obj.get("network_override"))
    decimals = config.get("decimals", 12)

    try:
        if account:
            account = resolve_ss58(account, config.get("wallet_path"))
        elif wallet_name:
            account = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide ACCOUNT (address or wallet name) or --wallet-name")
            return
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        raw = client.balance_of(keypair, account)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Token Balance", {
        "Account": account,
        "Balance": format_balance(raw, decimals),
        "Raw": raw,
    })


# ------------------------------------------------------------------
# approve
# ------------------------------------------------------------------

@token_group.command("approve")
@click.argument("spender", type=str)
@click.argument("amount", type=str)
@_wallet_option
@_network_option
@click.pass_context
def approve(ctx: click.Context, spender: str, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Approve a spender to use your TUSDT tokens.

    SPENDER can be an SS58 address or a bittensor wallet name.
    """
    config = load_config(network=network or ctx.obj.get("network_override"))
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 12)
    raw_amount = parse_balance(amount, decimals)

    try:
        spender = resolve_ss58(spender, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Approving {spender} to spend {amount} tokens...")

    try:
        client = TUSDTClient(config)
        result = client.approve(keypair, spender, raw_amount)
        print_success("Approval successful!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# allowance
# ------------------------------------------------------------------

@token_group.command("allowance")
@click.argument("owner", type=str)
@click.argument("spender", type=str)
@_network_option
@click.pass_context
def allowance(ctx: click.Context, owner: str, spender: str, network: str | None) -> None:
    """Show the allowance a spender has for an owner's tokens.

    OWNER and SPENDER can be SS58 addresses or bittensor wallet names.
    """
    config = load_config(network=network or ctx.obj.get("network_override"))
    decimals = config.get("decimals", 12)

    try:
        owner = resolve_ss58(owner, config.get("wallet_path"))
        spender = resolve_ss58(spender, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        raw = client.allowance(keypair, owner, spender)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Allowance", {
        "Owner": owner,
        "Spender": spender,
        "Allowance": format_balance(raw, decimals),
        "Raw": raw,
    })


# ------------------------------------------------------------------
# transfer
# ------------------------------------------------------------------

@token_group.command("transfer")
@click.argument("to", type=str)
@click.argument("amount", type=str)
@_wallet_option
@_network_option
@click.pass_context
def transfer(ctx: click.Context, to: str, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Transfer TUSDT tokens to another account.

    TO can be an SS58 address or a bittensor wallet name.
    """
    config = load_config(network=network or ctx.obj.get("network_override"))
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 12)
    raw_amount = parse_balance(amount, decimals)

    try:
        to = resolve_ss58(to, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))
        return

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))
        return

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Transferring {amount} tokens to {to}...")

    try:
        client = TUSDTClient(config)
        result = client.transfer(keypair, to, raw_amount)
        print_success("Transfer successful!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
