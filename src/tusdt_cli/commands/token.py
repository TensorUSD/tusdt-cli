"""Token (ERC-20) CLI commands."""

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    HelpfulCommand,
    ModeAwareGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair, resolve_ss58

_TOKEN_ADVANCED = {
    "mint",
    "burn",
    "increase-allowance",
    "decrease-allowance",
    "transfer-from",
    "set-controller",
    "add-minter",
    "remove-minter",
    "is-minter",
}


@click.group("token", cls=ModeAwareGroup, advanced_commands=_TOKEN_ADVANCED)
def token_group() -> None:
    """TUSDT token operations."""


# ------------------------------------------------------------------
# balance
# ------------------------------------------------------------------


@token_group.command("balance")
@click.option("--owner", default=None, help="Account SS58 address or wallet name (defaults to --wallet-name)")
@wallet_option
@network_option
@click.pass_context
def balance(ctx: click.Context, owner: str | None, wallet_name: str | None, network: str | None) -> None:
    """Show the TUSDT token balance for an account.

    \b
    Owner is resolved from --wallet-name, or pass --owner explicitly.
    Examples:
      tusdt token balance --wallet-name MyWallet
      tusdt token balance --owner 5GrwvaEF... --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    account = resolve_ss58((owner or state.wallet_name) or "", cfg.get("wallet_path"))
    kp = get_reader_keypair(cfg)
    raw = state.run_read(lambda c: c.balance_of(kp, account))

    state.output.detail(
        "Token Balance",
        {"Account": account, "Balance": format_balance(raw, decimals), "Raw": raw},
    )


# ------------------------------------------------------------------
# approve
# ------------------------------------------------------------------


@token_group.command("approve")
@click.argument("spender", type=str, metavar="<spender>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    spender = resolve_ss58(spender, cfg.get("wallet_path"))
    state.output.info(f"Approving {spender} to spend {amount} tokens...")

    state.submit(lambda c, kp: c.approve(kp, spender, raw_amount))
    state.output.success("Approval successful!")


# ------------------------------------------------------------------
# allowance
# ------------------------------------------------------------------


@token_group.command("allowance")
@click.argument("spender", type=str, metavar="<spender>")
@click.option("--owner", default=None, help="Owner SS58 address or wallet name (defaults to --wallet-name)")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)

    owner_addr = resolve_ss58((owner or state.wallet_name) or "", cfg.get("wallet_path"))
    spender_addr = resolve_ss58(spender, cfg.get("wallet_path"))
    kp = get_reader_keypair(cfg)
    raw = state.run_read(lambda c: c.allowance(kp, owner_addr, spender_addr))

    state.output.detail(
        "Allowance",
        {
            "Owner": owner_addr,
            "Spender": spender_addr,
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
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    to_addr = resolve_ss58(to, cfg.get("wallet_path"))
    state.output.info(f"Transferring {amount} tokens to {to_addr}...")

    state.submit(lambda c, kp: c.transfer(kp, to_addr, raw_amount))
    state.output.success("Transfer successful!")


# ------------------------------------------------------------------
# controller
# ------------------------------------------------------------------


@token_group.command("controller")
@network_option
@click.pass_context
def token_controller_cmd(ctx: click.Context, network: str | None) -> None:
    """Show the controller address of the TUSDT token contract.

    \b
    Examples:
      tusdt token controller
      tusdt token controller --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.token_controller(kp))
    state.output.detail("Token Controller", {"Address": addr})


# ------------------------------------------------------------------
# total-supply
# ------------------------------------------------------------------


@token_group.command("total-supply", cls=HelpfulCommand)
@network_option
@click.pass_context
def total_supply(ctx: click.Context, network: str | None) -> None:
    """View the total TUSDT token supply.

    \b
    Examples:
      tusdt token total-supply --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    raw_supply = state.run_read(lambda c: c.total_supply(kp))
    state.output.detail(
        "Total Supply", {"total_supply": format_balance(raw_supply, decimals), "raw": str(raw_supply)}
    )


# ------------------------------------------------------------------
# mint
# ------------------------------------------------------------------


@token_group.command("mint")
@click.argument("to", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    to_addr = resolve_ss58(to, cfg.get("wallet_path"))
    state.output.info(f"Minting {amount} tokens to {to_addr}...")

    state.submit(lambda c, kp: c.token_mint(kp, to_addr, raw_amount))
    state.output.success("Mint successful!")


# ------------------------------------------------------------------
# burn
# ------------------------------------------------------------------


@token_group.command("burn")
@click.argument("from_addr", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    from_addr = resolve_ss58(from_addr, cfg.get("wallet_path"))
    state.output.info(f"Burning {amount} tokens from {from_addr}...")

    state.submit(lambda c, kp: c.token_burn(kp, from_addr, raw_amount))
    state.output.success("Burn successful!")


# ------------------------------------------------------------------
# increase-allowance
# ------------------------------------------------------------------


@token_group.command("increase-allowance")
@click.argument("spender", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_delta = parse_balance(amount, decimals)

    spender = resolve_ss58(spender, cfg.get("wallet_path"))
    state.output.info(f"Increasing {spender}'s allowance by {amount} tokens...")

    state.submit(lambda c, kp: c.token_increase_allowance(kp, spender, raw_delta))
    state.output.success("Allowance increased!")


# ------------------------------------------------------------------
# decrease-allowance
# ------------------------------------------------------------------


@token_group.command("decrease-allowance")
@click.argument("spender", type=str, metavar="<ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_delta = parse_balance(amount, decimals)

    spender = resolve_ss58(spender, cfg.get("wallet_path"))
    state.output.info(f"Decreasing {spender}'s allowance by {amount} tokens...")

    state.submit(lambda c, kp: c.token_decrease_allowance(kp, spender, raw_delta))
    state.output.success("Allowance decreased!")


# ------------------------------------------------------------------
# transfer-from
# ------------------------------------------------------------------


@token_group.command("transfer-from")
@click.argument("from_addr", type=str, metavar="<from-ss58-address>")
@click.argument("to", type=str, metavar="<to-ss58-address>")
@click.argument("amount", type=str, metavar="<amount>")
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    from_addr = resolve_ss58(from_addr, cfg.get("wallet_path"))
    to_addr = resolve_ss58(to, cfg.get("wallet_path"))
    state.output.info(f"Transferring {amount} tokens from {from_addr} to {to_addr}...")

    state.submit(lambda c, kp: c.token_transfer_from(kp, from_addr, to_addr, raw_amount))
    state.output.success("Transfer successful!")


# ------------------------------------------------------------------
# set-controller
# ------------------------------------------------------------------


@token_group.command("set-controller")
@click.argument("address", type=str, metavar="<new-controller-address>")
@wallet_option
@network_option
@click.pass_context
def set_controller(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Transfer the token controller role to a new account (controller only).

    The old controller is removed as a minter; the new one is added.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Transferring controller to {address}...")
    state.submit(lambda c, kp: c.set_controller(kp, address))
    state.output.success(f"Controller transferred to {address}!")


# ------------------------------------------------------------------
# add-minter
# ------------------------------------------------------------------


@token_group.command("add-minter")
@click.argument("address", type=str, metavar="<minter-address>")
@wallet_option
@network_option
@click.pass_context
def add_minter(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Authorize an account to mint and burn tokens (controller only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Adding {address} as minter...")
    state.submit(lambda c, kp: c.add_minter(kp, address))
    state.output.success(f"{address} is now a minter!")


# ------------------------------------------------------------------
# remove-minter
# ------------------------------------------------------------------


@token_group.command("remove-minter")
@click.argument("address", type=str, metavar="<minter-address>")
@wallet_option
@network_option
@click.pass_context
def remove_minter(ctx: click.Context, address: str, wallet_name: str | None, network: str | None) -> None:
    """Revoke mint and burn authorization from an account (controller only)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Removing {address} from minters...")
    state.submit(lambda c, kp: c.remove_minter(kp, address))
    state.output.success(f"{address} is no longer a minter!")


# ------------------------------------------------------------------
# is-minter
# ------------------------------------------------------------------


@token_group.command("is-minter")
@click.argument("address", type=str, metavar="<account-address>")
@network_option
@click.pass_context
def is_minter(ctx: click.Context, address: str, network: str | None) -> None:
    """Check whether an account is an authorized minter."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    minter = state.run_read(lambda c: c.is_minter(kp, address))
    status = "yes" if minter else "no"
    state.output.detail(f"Minter: {address}", {"Is minter": status})
