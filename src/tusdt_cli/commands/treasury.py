"""Treasury CLI commands."""

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    HelpfulGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair

_FUND_CHOICE = click.Choice(
    ["emergency", "operation", "insurance", "dividend", "buyback", "voting"],
    case_sensitive=False,
)

_TOKEN_KIND_CHOICE = click.Choice(["tusdt", "native"], case_sensitive=False)


@click.group("treasury", cls=HelpfulGroup)
def treasury_group() -> None:
    """Treasury operations for the TUSDT system."""


# ======================================================================
# Basic (read) commands
# ======================================================================

# ------------------------------------------------------------------
# governance
# ------------------------------------------------------------------


@treasury_group.command("governance")
@network_option
@click.pass_context
def treasury_governance(ctx: click.Context, network: str | None) -> None:
    """Show the governance address registered in the treasury contract.

    \b
    Examples:
      tusdt treasury governance
      tusdt treasury governance --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.treasury_get_governance(kp))
    state.output.detail("Treasury Governance", {"Address": addr})


# ------------------------------------------------------------------
# token
# ------------------------------------------------------------------


@treasury_group.command("token")
@network_option
@click.pass_context
def treasury_token(ctx: click.Context, network: str | None) -> None:
    """Show the TUSDT token address registered in the treasury contract.

    \b
    Examples:
      tusdt treasury token
      tusdt treasury token --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    addr = state.run_read(lambda c: c.treasury_get_token(kp))
    state.output.detail("Treasury Token", {"Address": addr})


# ------------------------------------------------------------------
# fund-balance-tusdt
# ------------------------------------------------------------------


@treasury_group.command("fund-balance-tusdt")
@click.argument("fund", type=_FUND_CHOICE, metavar="<fund>")
@network_option
@click.pass_context
def fund_balance_tusdt(ctx: click.Context, fund: str, network: str | None) -> None:
    """Show the TUSDT balance for a specific fund.

    \b
    FUND is one of: emergency, operation, insurance, dividend, buyback, voting.
    Examples:
      tusdt treasury fund-balance-tusdt emergency
      tusdt treasury fund-balance-tusdt insurance --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    fund_dict = {fund.capitalize(): None}
    balance = state.run_read(lambda c: c.treasury_fund_balance_tusdt(kp, fund_dict))
    state.output.detail(
        f"Fund Balance – {fund.capitalize()} (TUSDT)",
        {"Fund": fund.capitalize(), "Balance": format_balance(balance, decimals), "Raw": balance},
    )


# ------------------------------------------------------------------
# fund-balance-native
# ------------------------------------------------------------------


@treasury_group.command("fund-balance-native")
@click.argument("fund", type=_FUND_CHOICE, metavar="<fund>")
@network_option
@click.pass_context
def fund_balance_native(ctx: click.Context, fund: str, network: str | None) -> None:
    """Show the native balance for a specific fund.

    \b
    FUND is one of: emergency, operation, insurance, dividend, buyback, voting.
    Examples:
      tusdt treasury fund-balance-native emergency
      tusdt treasury fund-balance-native insurance --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    fund_dict = {fund.capitalize(): None}
    balance = state.run_read(lambda c: c.treasury_fund_balance_native(kp, fund_dict))
    state.output.detail(
        f"Fund Balance – {fund.capitalize()} (Native)",
        {"Fund": fund.capitalize(), "Balance": format_balance(balance, decimals), "Raw": balance},
    )


# ------------------------------------------------------------------
# pending-tusdt
# ------------------------------------------------------------------


@treasury_group.command("pending-tusdt")
@network_option
@click.pass_context
def pending_tusdt(ctx: click.Context, network: str | None) -> None:
    """Show the total pending TUSDT balance awaiting distribution.

    \b
    Examples:
      tusdt treasury pending-tusdt
      tusdt treasury pending-tusdt --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    balance = state.run_read(lambda c: c.treasury_pending_tusdt(kp))
    state.output.detail("Pending TUSDT", {"Balance": format_balance(balance, decimals), "Raw": balance})


# ------------------------------------------------------------------
# pending-native
# ------------------------------------------------------------------


@treasury_group.command("pending-native")
@network_option
@click.pass_context
def pending_native(ctx: click.Context, network: str | None) -> None:
    """Show the total pending native balance awaiting distribution.

    \b
    Examples:
      tusdt treasury pending-native
      tusdt treasury pending-native --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    kp = get_reader_keypair(cfg)
    balance = state.run_read(lambda c: c.treasury_pending_native(kp))
    state.output.detail("Pending Native", {"Balance": format_balance(balance, decimals), "Raw": balance})


# ======================================================================
# Advanced (write) commands
# ======================================================================

# ------------------------------------------------------------------
# set-governance
# ------------------------------------------------------------------


@treasury_group.command("set-governance")
@click.argument("address", type=str, metavar="<ss58-address>")
@wallet_option
@network_option
@click.pass_context
def treasury_set_governance_cmd(
    ctx: click.Context, address: str, wallet_name: str | None, network: str | None
) -> None:
    """Set a new governance address for the treasury (governance only).

    \b
    ADDRESS is the SS58 address of the new governance account.
    Examples:
      tusdt treasury set-governance 5GrwvaEF... --wallet-name MyWallet
      tusdt treasury set-governance 5GrwvaEF... --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info(f"Setting treasury governance to {address}...")
    state.submit(lambda c, kp: c.treasury_set_governance(kp, address))
    state.output.success("Treasury governance updated!")


# ------------------------------------------------------------------
# distribute
# ------------------------------------------------------------------


@treasury_group.command("distribute")
@wallet_option
@network_option
@click.pass_context
def treasury_distribute_cmd(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Distribute pending TUSDT and native funds to their respective fund balances.

    \b
    Examples:
      tusdt treasury distribute --wallet-name MyWallet
      tusdt treasury distribute --wallet-name MyWallet --network testnet
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.output.info("Distributing pending funds to fund balances...")
    state.submit(lambda c, kp: c.treasury_distribute(kp))
    state.output.success("Funds distributed!")


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
@wallet_option
@network_option
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
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_amount = parse_balance(amount, decimals)

    fund_dict = {fund.capitalize(): None}
    token_kind_dict = {"Tusdt": None} if token_kind.lower() == "tusdt" else {"Native": None}

    state.output.info(f"Releasing {amount} {token_kind.upper()} from {fund} fund to {recipient}...")
    state.submit(lambda c, kp: c.treasury_release(kp, fund_dict, token_kind_dict, raw_amount, recipient))
    state.output.success("Funds released!")
