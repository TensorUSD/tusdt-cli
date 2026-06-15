"""Token (ERC-20) CLI commands."""

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
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair, resolve_ss58

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


_TOKEN_ADVANCED = {"mint", "burn", "increase-allowance", "decrease-allowance", "transfer-from"}


@click.group("token", cls=ModeAwareGroup, advanced_commands=_TOKEN_ADVANCED)
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
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

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

    print_dict(
        "Token Balance",
        {
            "Account": account,
            "Balance": format_balance(raw, decimals),
            "Raw": raw,
        },
    )


# ------------------------------------------------------------------
# approve
# ------------------------------------------------------------------


@token_group.command("approve")
@click.argument("spender", type=str, metavar="<spender>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def approve(
    ctx: click.Context, spender: str, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Approve a spender to use your TUSDT tokens.

    \b
    SPENDER is the SS58 address or wallet name of the account to approve.
    AMOUNT  is the human-readable token amount to approve (e.g. 1000).
    Examples:
      tusdt token approve 5GrwvaEF... 1000 --wallet-name MyWallet
      tusdt token approve SpenderWallet 500.5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    try:
        spender = resolve_ss58(spender, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

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
@click.argument("spender", type=str, metavar="<spender>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@_wallet_option
@_network_option
@click.pass_context
def allowance(
    ctx: click.Context, spender: str, owner: str | None, wallet_name: str | None, network: str | None
) -> None:
    """Show the allowance a spender has for an owner's tokens.

    \b
    SPENDER is the SS58 address or wallet name of the spender account.
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt token allowance 5GrwvaEF... --wallet-name MyWallet
      tusdt token allowance SpenderWallet --owner 5Abc123... --network testnet
    """
    config = load_config(network=network)
    decimals = config.get("decimals", 9)

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

    print_dict(
        "Allowance",
        {
            "Owner": owner,
            "Spender": spender,
            "Allowance": format_balance(raw, decimals),
            "Raw": raw,
        },
    )


# ------------------------------------------------------------------
# transfer
# ------------------------------------------------------------------


@token_group.command("transfer")
@click.argument("to", type=str, metavar="<recipient>")
@click.argument("amount", type=str, metavar="<amount>")
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
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    try:
        to = resolve_ss58(to, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Transferring {amount} tokens to {to}...")

    try:
        client = TUSDTClient(config)
        result = client.transfer(keypair, to, raw_amount)
        print_success("Transfer successful!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# controller
# ------------------------------------------------------------------


@token_group.command("controller")
@_network_option
@click.pass_context
def token_controller_cmd(ctx: click.Context, network: str | None) -> None:
    """Show the controller address of the TUSDT token contract.

    \b
    Examples:
      tusdt token controller
      tusdt token controller --network testnet
    """
    config = load_config(network=network)

    try:
        keypair = get_reader_keypair(config)
        client = TUSDTClient(config)
        addr = client.token_controller(keypair)
    except Exception as exc:
        print_error(str(exc))
        return

    print_dict("Token Controller", {"Address": addr})


# ------------------------------------------------------------------
# mint
# ------------------------------------------------------------------


@token_group.command("mint")
@click.argument("to", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def mint(ctx: click.Context, to: str, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Mint TUSDT tokens to an account (controller only).

    \b
    TO     is the SS58 address of the recipient.
    AMOUNT is the human-readable token amount to mint (e.g. 1000).
    Examples:
      tusdt token mint 5GrwvaEF... 1000 --wallet-name MyWallet
      tusdt token mint 5GrwvaEF... 500.5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    try:
        to = resolve_ss58(to, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Minting {amount} tokens to {to}...")

    try:
        client = TUSDTClient(config)
        result = client.token_mint(keypair, to, raw_amount)
        print_success("Mint successful!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# burn
# ------------------------------------------------------------------


@token_group.command("burn")
@click.argument("from_addr", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def burn(
    ctx: click.Context, from_addr: str, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Burn TUSDT tokens from an account (controller only).

    \b
    FROM   is the SS58 address to burn tokens from.
    AMOUNT is the human-readable token amount to burn (e.g. 1000).
    Examples:
      tusdt token burn 5GrwvaEF... 1000 --wallet-name MyWallet
      tusdt token burn 5GrwvaEF... 500.5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    try:
        from_addr = resolve_ss58(from_addr, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Burning {amount} tokens from {from_addr}...")

    try:
        client = TUSDTClient(config)
        result = client.token_burn(keypair, from_addr, raw_amount)
        print_success("Burn successful!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# increase-allowance
# ------------------------------------------------------------------


@token_group.command("increase-allowance")
@click.argument("spender", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def increase_allowance_cmd(
    ctx: click.Context, spender: str, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Increase a spender's allowance by a given amount.

    \b
    SPENDER is the SS58 address of the spender account.
    AMOUNT  is the human-readable token amount to add to the allowance (e.g. 1000).
    Examples:
      tusdt token increase-allowance 5GrwvaEF... 1000 --wallet-name MyWallet
      tusdt token increase-allowance 5GrwvaEF... 500.5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_delta = parse_balance(amount, decimals)

    try:
        spender = resolve_ss58(spender, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Increasing {spender}'s allowance by {amount} tokens...")

    try:
        client = TUSDTClient(config)
        result = client.token_increase_allowance(keypair, spender, raw_delta)
        print_success("Allowance increased!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# decrease-allowance
# ------------------------------------------------------------------


@token_group.command("decrease-allowance")
@click.argument("spender", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def decrease_allowance_cmd(
    ctx: click.Context, spender: str, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Decrease a spender's allowance by a given amount.

    \b
    SPENDER is the SS58 address of the spender account.
    AMOUNT  is the human-readable token amount to subtract from the allowance (e.g. 1000).
    Examples:
      tusdt token decrease-allowance 5GrwvaEF... 1000 --wallet-name MyWallet
      tusdt token decrease-allowance 5GrwvaEF... 500.5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_delta = parse_balance(amount, decimals)

    try:
        spender = resolve_ss58(spender, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Decreasing {spender}'s allowance by {amount} tokens...")

    try:
        client = TUSDTClient(config)
        result = client.token_decrease_allowance(keypair, spender, raw_delta)
        print_success("Allowance decreased!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))


# ------------------------------------------------------------------
# transfer-from
# ------------------------------------------------------------------


@token_group.command("transfer-from")
@click.argument("from_addr", type=str, metavar="<from-ss58-address>")
@click.argument("to", type=str, metavar="<to-ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@_wallet_option
@_network_option
@click.pass_context
def transfer_from_cmd(
    ctx: click.Context,
    from_addr: str,
    to: str,
    amount: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Transfer TUSDT tokens from one account to another (requires allowance).

    \b
    FROM   is the SS58 address to transfer tokens from.
    TO     is the SS58 address of the recipient.
    AMOUNT is the human-readable token amount to transfer (e.g. 1000).
    Examples:
      tusdt token transfer-from 5GrwvaEF... 5FHneW... 1000 --wallet-name MyWallet
      tusdt token transfer-from 5GrwvaEF... 5FHneW... 500.5 --wallet-name MyWallet --network testnet
    """
    config = load_config(network=network)
    if wallet_name:
        config["wallet_name"] = wallet_name
    decimals = config.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    try:
        from_addr = resolve_ss58(from_addr, config.get("wallet_path"))
        to = resolve_ss58(to, config.get("wallet_path"))
    except Exception as exc:
        print_error(str(exc))

    try:
        keypair = get_signer_keypair(config)
    except Exception as exc:
        print_error(str(exc))

    print_info(f"Signer: {keypair.ss58_address}")
    print_info(f"Transferring {amount} tokens from {from_addr} to {to}...")

    try:
        client = TUSDTClient(config)
        result = client.token_transfer_from(keypair, from_addr, to, raw_amount)
        print_success("Transfer successful!")
        print_tx_result(result, config.get("network", "finney"))
    except Exception as exc:
        print_error(str(exc))
