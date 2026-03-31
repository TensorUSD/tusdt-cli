"""Token (ERC-20) CLI commands."""

import click

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import load_config, NETWORKS
from tusdt_cli.utils import (
    ContractError,
    HelpfulGroup,
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


@click.group("token", cls=HelpfulGroup)
def token_group() -> None:
    """TUSDT token operations."""


# ------------------------------------------------------------------
# balance
# ------------------------------------------------------------------

@token_group.command("balance")
@click.option("--owner", default=None, help="Account SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def balance(ctx: click.Context, owner: str | None, wallet_name: str | None, network: str | None) -> None:
    """Show the TUSDT token balance for an account.

    \b
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt token balance --wallet-name MyWallet
      tusdt token balance --owner 5GrwvaEF... --network testnet
    """
    config = load_config(network=network or ctx.obj.get("network_override"))
    decimals = config.get("decimals", 12)

    try:
        if owner:
            account = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            account = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
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

    \b
    SPENDER is the SS58 address or wallet name of the account to approve.
    AMOUNT  is the human-readable token amount to approve (e.g. 1000).
    Examples:
      tusdt token approve 5GrwvaEF... 1000 --wallet-name MyWallet
      tusdt token approve SpenderWallet 500.5 --wallet-name MyWallet --network testnet
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
@click.argument("spender", type=str)
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def allowance(ctx: click.Context, spender: str, owner: str | None, wallet_name: str | None, network: str | None) -> None:
    """Show the allowance a spender has for an owner's tokens.

    \b
    SPENDER is the SS58 address or wallet name of the spender account.
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt token allowance 5GrwvaEF... --wallet-name MyWallet
      tusdt token allowance SpenderWallet --owner 5Abc123... --network testnet
    """
    config = load_config(network=network or ctx.obj.get("network_override"))
    decimals = config.get("decimals", 12)

    try:
        if owner:
            owner = resolve_ss58(owner, config.get("wallet_path"))
        elif wallet_name:
            owner = resolve_ss58(wallet_name, config.get("wallet_path"))
        else:
            print_error("Provide --owner (address or wallet name) or --wallet-name")
            return
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

    \b
    TO     is the SS58 address or wallet name of the recipient.
    AMOUNT is the human-readable token amount to send (e.g. 50).
    Examples:
      tusdt token transfer 5GrwvaEF... 50 --wallet-name MyWallet
      tusdt token transfer RecipientWallet 100.5 --wallet-name MyWallet --network testnet
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
