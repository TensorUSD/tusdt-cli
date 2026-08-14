"""Lending pool CLI commands."""

import click

from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    HelpfulGroup,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair


@click.group("lending", cls=HelpfulGroup)
def lending_group() -> None:
    """Manage the TUSDT lending pool — supply, borrow, and alpha collateral."""


# ======================================================================
# Supply / Withdraw
# ======================================================================


@lending_group.command("supply-tao")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def supply_tao(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Supply native TAO to the lending pool and receive lTAO.

    Attaches native TAO as the transferred value.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_supply_tao(kp, raw_amount))
    state.output.success("TAO supplied successfully!")


@lending_group.command("supply-tusdt")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def supply_tusdt(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Supply TUSDT to the lending pool and receive lTUSDT.

    Requires prior token approval: tusdt token approve <pool_address> <amount>
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_supply_tusdt(kp, raw_amount))
    state.output.success("TUSDT supplied successfully!")


@lending_group.command("withdraw-tao")
@click.argument("ltoken_amount", metavar="<ltoken_amount>")
@wallet_option
@network_option
@click.pass_context
def withdraw_tao(
    ctx: click.Context, ltoken_amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Withdraw native TAO by burning lTAO tokens."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(ltoken_amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_withdraw_tao(kp, raw_amount))
    state.output.success("TAO withdrawn successfully!")


@lending_group.command("withdraw-tusdt")
@click.argument("ltoken_amount", metavar="<ltoken_amount>")
@wallet_option
@network_option
@click.pass_context
def withdraw_tusdt(
    ctx: click.Context, ltoken_amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Withdraw TUSDT by burning lTUSDT tokens."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(ltoken_amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_withdraw_tusdt(kp, raw_amount))
    state.output.success("TUSDT withdrawn successfully!")


# ======================================================================
# Borrow / Repay
# ======================================================================


@lending_group.command("borrow-tao")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def borrow_tao(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Borrow native TAO against your alpha collateral."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_borrow_tao(kp, raw_amount))
    state.output.success("TAO borrowed successfully!")


@lending_group.command("borrow-tusdt")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def borrow_tusdt(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Borrow TUSDT against your alpha collateral."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_borrow_tusdt(kp, raw_amount))
    state.output.success("TUSDT borrowed successfully!")


@lending_group.command("repay-tao")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def repay_tao(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Repay a TAO loan. Attaches native TAO as the transferred value."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_repay_tao(kp, raw_amount))
    state.output.success("TAO repaid successfully!")


@lending_group.command("repay-tusdt")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def repay_tusdt(ctx: click.Context, amount: str, wallet_name: str | None, network: str | None) -> None:
    """Repay a TUSDT loan. Requires prior token approval."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_repay_tusdt(kp, raw_amount))
    state.output.success("TUSDT repaid successfully!")


# ======================================================================
# Alpha Collateral
# ======================================================================


@lending_group.command("deposit-alpha")
@click.option("--netuid", required=True, type=int, help="Subnet netuid for alpha collateral")
@click.option("--amount", required=True, help="Alpha amount to deposit")
@wallet_option
@network_option
@click.pass_context
def deposit_alpha(
    ctx: click.Context,
    netuid: int,
    amount: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Deposit alpha stake as collateral into the lending pool.

    Uses atomic pull via chain extension — the caller's stake must be
    under the pool's hotkey.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_deposit_alpha(kp, netuid, raw_amount))
    state.output.success("Alpha deposited successfully!")


@lending_group.command("withdraw-alpha")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@click.option("--amount", required=True, help="Alpha principal amount to withdraw")
@click.option("--dest-coldkey", required=True, help="Destination coldkey SS58 address")
@wallet_option
@network_option
@click.pass_context
def withdraw_alpha(
    ctx: click.Context,
    netuid: int,
    amount: str,
    dest_coldkey: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Withdraw alpha collateral from the lending pool.

    Rejects if health factor would fall below 1.0 after withdrawal.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_withdraw_alpha(kp, netuid, raw_amount, dest_coldkey))
    state.output.success("Alpha withdrawn successfully!")


# ======================================================================
# Liquidation
# ======================================================================


@lending_group.command("liquidate")
@click.option("--borrower", required=True, help="Borrower SS58 address to liquidate")
@click.option("--debt-market", required=True, type=int, help="Debt market: 0 for TAO, 1 for TUSDT")
@click.option("--debt-to-cover", required=True, help="Amount of debt to cover")
@click.option("--collateral-netuid", required=True, type=int, help="Collateral netuid to seize")
@wallet_option
@network_option
@click.pass_context
def liquidate(
    ctx: click.Context,
    borrower: str,
    debt_market: int,
    debt_to_cover: str,
    collateral_netuid: int,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Liquidate an underwater borrower.

    For debt_market=0 (TAO), attaches native TAO as transferred value.
    For debt_market=1 (TUSDT), requires prior token approval.
    Close factor caps the debt covered to 50 percent of the borrower's total debt.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_debt = parse_balance(debt_to_cover, cfg.get("decimals", 9))
    value = raw_debt if debt_market == 0 else 0
    state.submit(
        lambda c, kp: c.lending_liquidate(
            kp,
            borrower,
            debt_market,
            raw_debt,
            collateral_netuid,
            value=value,
        )
    )
    state.output.success("Liquidation submitted successfully!")


# ======================================================================
# Permissionless Claims
# ======================================================================


@lending_group.command("claim-alpha-yield")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def claim_alpha_yield(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Claim alpha staking yield for a netuid (permissionless).

    25 percent performance fee goes to the treasury; 75 percent grows the yield index.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_claim_alpha_yield(kp, netuid))
    state.output.success("Alpha yield claimed!")


@lending_group.command("claim-reserve")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@wallet_option
@network_option
@click.pass_context
def claim_reserve(ctx: click.Context, market_id: int, wallet_name: str | None, network: str | None) -> None:
    """Claim accrued protocol reserve for a market (permissionless)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_claim_reserve(kp, market_id))
    state.output.success("Reserve claimed!")


# ======================================================================
# Governance: Alpha Market Management
# ======================================================================


@lending_group.command("set-approved-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@click.option("--approve/--revoke", default=True, help="Approve (default) or revoke the subnet")
@wallet_option
@network_option
@click.pass_context
def set_approved_netuid(
    ctx: click.Context,
    netuid: int,
    approve: bool,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Approve or revoke a subnet for alpha collateral. Governance only.

    Revoking fails if the netuid has active positions.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    action = "Approving" if approve else "Revoking"
    state.output.info(f"{action} subnet {netuid}...")
    state.submit(lambda c, kp: c.lending_set_approved_netuid(kp, netuid, approve))
    state.output.success(f"Subnet {netuid} {'approved' if approve else 'revoked'}!")


@lending_group.command("set-alpha-params")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@click.option(
    "--collateral-factor", type=int, default=None, help="Collateral factor in BPS (e.g. 5000 = 50%)"
)
@click.option("--liquidation-threshold", type=int, default=None, help="Liquidation threshold in BPS")
@click.option("--liquidation-bonus", type=int, default=None, help="Liquidation bonus in BPS")
@click.option("--supply-cap", type=str, default=None, help="Supply cap (0 = unlimited)")
@wallet_option
@network_option
@click.pass_context
def set_alpha_params(
    ctx: click.Context,
    netuid: int,
    collateral_factor: int | None,
    liquidation_threshold: int | None,
    liquidation_bonus: int | None,
    supply_cap: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule alpha market params update (60s timelock). Governance only.

    Reads current params first, then merges the provided values.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_supply_cap = parse_balance(supply_cap, decimals) if supply_cap is not None else None

    def _merge(c, kp):
        current = c.lending_get_alpha_markets(kp)
        existing: dict = {}
        if isinstance(current, list):
            for item in current:
                if isinstance(item, (list, tuple)) and len(item) == 2 and item[0] == netuid:
                    existing = item[1] if isinstance(item[1], dict) else {}
                    break
        config = {
            "collateral_factor": collateral_factor
            if collateral_factor is not None
            else existing.get("collateral_factor", 0),
            "liquidation_threshold": liquidation_threshold
            if liquidation_threshold is not None
            else existing.get("liquidation_threshold", 0),
            "liquidation_bonus": liquidation_bonus
            if liquidation_bonus is not None
            else existing.get("liquidation_bonus", 0),
            "supply_cap": raw_supply_cap if raw_supply_cap is not None else existing.get("supply_cap", 0),
        }
        return c.lending_set_alpha_params(kp, netuid, config)

    state.submit(lambda c, kp: _merge(c, kp))
    state.output.success("Alpha params update scheduled (60s timelock).")


@lending_group.command("execute-alpha-params-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def execute_alpha_params_update(
    ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None
) -> None:
    """Execute a pending alpha params update (permissionless, time-gated)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_execute_alpha_params_update(kp, netuid))
    state.output.success("Alpha params update executed!")


@lending_group.command("cancel-alpha-params-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def cancel_alpha_params_update(
    ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None
) -> None:
    """Cancel a pending alpha params update. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_cancel_alpha_params_update(kp, netuid))
    state.output.success("Alpha params update cancelled!")


# ======================================================================
# Governance: Interest Rate Params
# ======================================================================


@lending_group.command("set-market-params")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@click.option("--base-rate", type=int, default=None, help="Base borrow rate in BPS")
@click.option("--slope1", type=int, default=None, help="Slope1 rate in BPS (before optimal utilization)")
@click.option("--slope2", type=int, default=None, help="Slope2 rate in BPS (after optimal utilization)")
@click.option(
    "--optimal-utilization", type=int, default=None, help="Optimal utilization in BPS (e.g. 8000 = 80%)"
)
@click.option("--reserve-factor", type=int, default=None, help="Reserve factor in BPS")
@wallet_option
@network_option
@click.pass_context
def set_market_params(
    ctx: click.Context,
    market_id: int,
    base_rate: int | None,
    slope1: int | None,
    slope2: int | None,
    optimal_utilization: int | None,
    reserve_factor: int | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule market interest rate params update (60s timelock). Governance only.

    Reads current params first, then merges the provided values.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()

    def _merge(c, kp):
        current = c.lending_get_market_state(kp, market_id)
        base = current if isinstance(current, dict) else {}
        config = {
            "base_rate": base_rate if base_rate is not None else base.get("base_rate", 0),
            "slope1": slope1 if slope1 is not None else base.get("slope1", 0),
            "slope2": slope2 if slope2 is not None else base.get("slope2", 0),
            "optimal_utilization": optimal_utilization
            if optimal_utilization is not None
            else base.get("optimal_utilization", 0),
            "reserve_factor": reserve_factor if reserve_factor is not None else base.get("reserve_factor", 0),
        }
        return c.lending_set_market_params(kp, market_id, config)

    state.submit(lambda c, kp: _merge(c, kp))
    state.output.success("Market params update scheduled (60s timelock).")


@lending_group.command("execute-market-params-update")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@wallet_option
@network_option
@click.pass_context
def execute_market_params_update(
    ctx: click.Context, market_id: int, wallet_name: str | None, network: str | None
) -> None:
    """Execute a pending market params update (permissionless, time-gated)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_execute_market_params_update(kp, market_id))
    state.output.success("Market params update executed!")


@lending_group.command("cancel-market-params-update")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@wallet_option
@network_option
@click.pass_context
def cancel_market_params_update(
    ctx: click.Context, market_id: int, wallet_name: str | None, network: str | None
) -> None:
    """Cancel a pending market params update. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_cancel_market_params_update(kp, market_id))
    state.output.success("Market params update cancelled!")


# ======================================================================
# Governance: Global Params
# ======================================================================


@lending_group.command("set-global-params")
@click.option("--max-oracle-age-ms", type=int, default=None, help="Maximum oracle price age in ms")
@click.option("--close-factor", type=int, default=None, help="Close factor in BPS (e.g. 5000 = 50%)")
@click.option("--performance-fee", type=int, default=None, help="Performance fee in BPS")
@click.option("--supply-cap-tao", type=str, default=None, help="TAO supply cap (0 = unlimited)")
@click.option("--supply-cap-tusdt", type=str, default=None, help="TUSDT supply cap (0 = unlimited)")
@click.option("--borrow-cap-tao", type=str, default=None, help="TAO borrow cap (0 = unlimited)")
@click.option("--borrow-cap-tusdt", type=str, default=None, help="TUSDT borrow cap (0 = unlimited)")
@wallet_option
@network_option
@click.pass_context
def set_global_params(
    ctx: click.Context,
    max_oracle_age_ms: int | None,
    close_factor: int | None,
    performance_fee: int | None,
    supply_cap_tao: str | None,
    supply_cap_tusdt: str | None,
    borrow_cap_tao: str | None,
    borrow_cap_tusdt: str | None,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Schedule global params update (60s timelock). Governance only.

    Only provided options are changed; others keep their current values.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    config: dict = {}
    if max_oracle_age_ms is not None:
        config["max_oracle_age_ms"] = max_oracle_age_ms
    if close_factor is not None:
        config["close_factor"] = close_factor
    if performance_fee is not None:
        config["performance_fee"] = performance_fee
    if supply_cap_tao is not None:
        config["supply_cap_tao"] = parse_balance(supply_cap_tao, decimals)
    if supply_cap_tusdt is not None:
        config["supply_cap_tusdt"] = parse_balance(supply_cap_tusdt, decimals)
    if borrow_cap_tao is not None:
        config["borrow_cap_tao"] = parse_balance(borrow_cap_tao, decimals)
    if borrow_cap_tusdt is not None:
        config["borrow_cap_tusdt"] = parse_balance(borrow_cap_tusdt, decimals)
    state.submit(lambda c, kp: c.lending_set_global_params(kp, config))
    state.output.success("Global params update scheduled (60s timelock).")


@lending_group.command("execute-global-params-update")
@wallet_option
@network_option
@click.pass_context
def execute_global_params_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Execute a pending global params update (permissionless, time-gated)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_execute_global_params_update(kp))
    state.output.success("Global params update executed!")


@lending_group.command("cancel-global-params-update")
@wallet_option
@network_option
@click.pass_context
def cancel_global_params_update(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Cancel a pending global params update. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_cancel_global_params_update(kp))
    state.output.success("Global params update cancelled!")


# ======================================================================
# Governance: Roles & Addresses
# ======================================================================


@lending_group.command("update-governance")
@click.argument("new_governance", metavar="<new-governance-address>")
@wallet_option
@network_option
@click.pass_context
def update_governance(
    ctx: click.Context, new_governance: str, wallet_name: str | None, network: str | None
) -> None:
    """Transfer the lending pool governance role. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_update_governance(kp, new_governance))
    state.output.success("Governance updated!")


@lending_group.command("update-treasury")
@click.argument("new_treasury", metavar="<new-treasury-address>")
@wallet_option
@network_option
@click.pass_context
def update_treasury(
    ctx: click.Context, new_treasury: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the lending pool treasury address. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_update_treasury(kp, new_treasury))
    state.output.success("Treasury updated!")


@lending_group.command("update-platform")
@click.argument("new_platform", metavar="<new-platform-address>")
@wallet_option
@network_option
@click.pass_context
def update_platform(
    ctx: click.Context, new_platform: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the lending pool platform (pause operator) address. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_update_platform(kp, new_platform))
    state.output.success("Platform updated!")


@lending_group.command("update-oracle-address")
@click.argument("new_oracle", metavar="<new-oracle-address>")
@wallet_option
@network_option
@click.pass_context
def update_oracle_address(
    ctx: click.Context, new_oracle: str, wallet_name: str | None, network: str | None
) -> None:
    """Update the lending pool oracle address. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_update_oracle_address(kp, new_oracle))
    state.output.success("Oracle address updated!")


@lending_group.command("update-ltoken-address")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@click.argument("new_ltoken", metavar="<new-ltoken-address>")
@wallet_option
@network_option
@click.pass_context
def update_ltoken_address(
    ctx: click.Context,
    market_id: int,
    new_ltoken: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update an lToken child contract address. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_update_ltoken_address(kp, market_id, new_ltoken))
    state.output.success("LToken address updated!")


@lending_group.command("update-pool-hotkey")
@click.option("--new-hotkey", required=True, help="New pool hotkey SS58 address")
@click.option(
    "--netuid",
    "netuids",
    type=int,
    multiple=True,
    required=True,
    help="Subnet netuids to migrate stake for (repeatable)",
)
@wallet_option
@network_option
@click.pass_context
def update_pool_hotkey(
    ctx: click.Context,
    new_hotkey: str,
    netuids: tuple[int, ...],
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Migrate all alpha stake to a new pool hotkey. Governance only. Max 32 netuids."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_update_pool_hotkey(kp, new_hotkey, list(netuids)))
    state.output.success("Pool hotkey updated!")


@lending_group.command("claim-surplus-tusdt")
@click.argument("amount", metavar="<amount>")
@wallet_option
@network_option
@click.pass_context
def claim_surplus_tusdt(
    ctx: click.Context, amount: str, wallet_name: str | None, network: str | None
) -> None:
    """Claim surplus TUSDT held by the lending pool to the treasury. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))
    state.submit(lambda c, kp: c.lending_claim_surplus_tusdt(kp, raw_amount))
    state.output.success("Surplus TUSDT claimed!")


# ======================================================================
# Emergency
# ======================================================================


@lending_group.command("pause")
@wallet_option
@network_option
@click.pass_context
def pause(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Pause the lending pool. Governance or platform only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_pause(kp))
    state.output.success("Lending pool paused!")


@lending_group.command("unpause")
@wallet_option
@network_option
@click.pass_context
def unpause(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Unpause the lending pool. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_unpause(kp))
    state.output.success("Lending pool unpaused!")


# ======================================================================
# Native Sweep
# ======================================================================


@lending_group.command("transfer-native-to-treasury")
@wallet_option
@network_option
@click.pass_context
def transfer_native_to_treasury(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Sweep the lending pool's native TAO balance to the treasury. Governance only."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_transfer_native_to_treasury(kp))
    state.output.success("Native balance transferred to treasury!")


# ======================================================================
# Queries / Getters
# ======================================================================


@lending_group.command("market-state")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def market_state(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show market state (supply, debt, rates, reserve)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_market_state(kp, market_id))
    state.output.detail("Market State", {"Result": result})


@lending_group.command("position")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@click.option("--user", required=True, help="User SS58 address")
@network_option
@click.pass_context
def position(ctx: click.Context, market_id: int, user: str, network: str | None) -> None:
    """Show a user's position in a lending market."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_position(kp, market_id, user))
    state.output.detail("Position", {"Result": result})


@lending_group.command("exchange-rate")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def exchange_rate(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show lToken exchange rate for a market (1e18 scale)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_exchange_rate(kp, market_id))
    state.output.detail("Exchange Rate", {"Result": result})


@lending_group.command("borrow-index")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def borrow_index(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show borrow index for a market (1e18 scale)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_borrow_index(kp, market_id))
    state.output.detail("Borrow Index", {"Result": result})


@lending_group.command("utilization")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def utilization(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show utilization ratio for a market (1e18 scale)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_utilization(kp, market_id))
    state.output.detail("Utilization", {"Result": result})


@lending_group.command("borrow-rate")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def borrow_rate(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show current borrow rate for a market (1e18 scale)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_borrow_rate(kp, market_id))
    state.output.detail("Borrow Rate", {"Result": result})


@lending_group.command("supply-rate")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def supply_rate(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show current supply rate for a market (1e18 scale)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_supply_rate(kp, market_id))
    state.output.detail("Supply Rate", {"Result": result})


@lending_group.command("underlying-balance")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@click.option("--user", required=True, help="User SS58 address")
@network_option
@click.pass_context
def underlying_balance(ctx: click.Context, market_id: int, user: str, network: str | None) -> None:
    """Show a user's underlying balance in a market."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_underlying_balance(kp, market_id, user))
    state.output.detail("Underlying Balance", {"Result": result})


@lending_group.command("user-debt")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@click.option("--user", required=True, help="User SS58 address")
@network_option
@click.pass_context
def user_debt(ctx: click.Context, market_id: int, user: str, network: str | None) -> None:
    """Show a user's debt in a market."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_user_debt(kp, market_id, user))
    state.output.detail("User Debt", {"Result": result})


@lending_group.command("user-debt-details")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@click.option("--user", required=True, help="User SS58 address")
@network_option
@click.pass_context
def user_debt_details(ctx: click.Context, market_id: int, user: str, network: str | None) -> None:
    """Show a user's debt, principal, and accrued interest in a market.

    Falls back to the plain debt when the deployed pool predates principal
    tracking.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_user_debt_details(kp, market_id, user))
    if result is None:
        debt = state.run_read(lambda c: c.lending_get_user_debt(kp, market_id, user))
        state.output.detail(
            "User Debt Details",
            {"Debt": debt, "Interest": "unavailable (deployed pool predates principal tracking)"},
        )
        return
    debt, principal = result
    state.output.detail(
        "User Debt Details",
        {"Debt": debt, "Principal": principal, "Interest": debt - principal},
    )


@lending_group.command("alpha-markets")
@network_option
@click.pass_context
def alpha_markets(ctx: click.Context, network: str | None) -> None:
    """List all approved alpha markets with their params."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_alpha_markets(kp))
    state.output.detail("Alpha Markets", {"Result": result})


@lending_group.command("alpha-position")
@click.option("--user", required=True, help="User SS58 address")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@network_option
@click.pass_context
def alpha_position(ctx: click.Context, user: str, netuid: int, network: str | None) -> None:
    """Show a user's alpha collateral position for a netuid."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_user_alpha_position(kp, user, netuid))
    state.output.detail("Alpha Position", {"Result": result})


@lending_group.command("alpha-yield-index")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@network_option
@click.pass_context
def alpha_yield_index(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Show the yield index for a netuid (1e18 scale)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_alpha_yield_index(kp, netuid))
    state.output.detail("Alpha Yield Index", {"Result": result})


@lending_group.command("netuid-total-collateral")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@network_option
@click.pass_context
def netuid_total_collateral(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Show total alpha collateral deposited for a netuid."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_netuid_total_collateral(kp, netuid))
    state.output.detail("Netuid Total Collateral", {"Result": result})


@lending_group.command("is-approved-netuid")
@click.argument("netuid", type=int, metavar="<netuid>")
@network_option
@click.pass_context
def is_approved_netuid(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Check if a subnet is approved for alpha collateral."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_is_approved_netuid(kp, netuid))
    state.output.detail("Netuid Approval", {"Result": result})


@lending_group.command("active-netuids-count")
@network_option
@click.pass_context
def active_netuids_count(ctx: click.Context, network: str | None) -> None:
    """Show the number of approved alpha netuids."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_active_netuids_count(kp))
    state.output.detail("Active Netuids", {"Result": result})


@lending_group.command("positions")
@click.option("--user", required=True, help="User SS58 address")
@click.option("--page", type=int, default=0, help="Page number (10 per page)")
@network_option
@click.pass_context
def positions(ctx: click.Context, user: str, page: int, network: str | None) -> None:
    """List a user's positions across all markets."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_positions(kp, user, page))
    state.output.detail("Positions", {"Result": result})


@lending_group.command("all-positions")
@click.option("--page", type=int, default=0, help="Page number (10 per page)")
@network_option
@click.pass_context
def all_positions(ctx: click.Context, page: int, network: str | None) -> None:
    """List all positions across all users (paginated)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_all_positions(kp, page))
    state.output.detail("All Positions", {"Result": result})


@lending_group.command("pending-alpha-params-update")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@network_option
@click.pass_context
def pending_alpha_params_update(ctx: click.Context, netuid: int, network: str | None) -> None:
    """Show pending alpha params update for a netuid."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_pending_alpha_params_update(kp, netuid))
    state.output.detail("Pending Alpha Params Update", {"Result": result})


@lending_group.command("pending-market-params-update")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def pending_market_params_update(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show pending market params update for a market."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_pending_market_params_update(kp, market_id))
    state.output.detail("Pending Market Params Update", {"Result": result})


@lending_group.command("pending-global-params-update")
@network_option
@click.pass_context
def pending_global_params_update(ctx: click.Context, network: str | None) -> None:
    """Show pending global params update."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_pending_global_params_update(kp))
    state.output.detail("Pending Global Params Update", {"Result": result})


@lending_group.command("governance")
@network_option
@click.pass_context
def governance(ctx: click.Context, network: str | None) -> None:
    """Show the lending pool governance address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_governance(kp))
    state.output.detail("Governance", {"Address": result})


@lending_group.command("treasury")
@network_option
@click.pass_context
def treasury(ctx: click.Context, network: str | None) -> None:
    """Show the lending pool treasury address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_treasury(kp))
    state.output.detail("Treasury", {"Address": result})


@lending_group.command("platform")
@network_option
@click.pass_context
def platform(ctx: click.Context, network: str | None) -> None:
    """Show the lending pool platform (pause operator) address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_platform(kp))
    state.output.detail("Platform", {"Address": result})


@lending_group.command("paused")
@network_option
@click.pass_context
def paused(ctx: click.Context, network: str | None) -> None:
    """Check if the lending pool is paused."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_is_paused(kp))
    state.output.detail("Contract Status", {"Paused": result})


@lending_group.command("oracle-address")
@network_option
@click.pass_context
def oracle_address(ctx: click.Context, network: str | None) -> None:
    """Show the lending pool oracle address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_oracle_address(kp))
    state.output.detail("Oracle Address", {"Address": result})


@lending_group.command("tusdt-address")
@network_option
@click.pass_context
def tusdt_address(ctx: click.Context, network: str | None) -> None:
    """Show the lending pool TUSDT token address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_tusdt_address(kp))
    state.output.detail("TUSDT Address", {"Address": result})


@lending_group.command("ltoken-address")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def ltoken_address(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show an lToken child contract address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_ltoken_address(kp, market_id))
    state.output.detail("LToken Address", {"Address": result})


@lending_group.command("pool-hotkey")
@network_option
@click.pass_context
def pool_hotkey(ctx: click.Context, network: str | None) -> None:
    """Show the lending pool hotkey address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_pool_hotkey(kp))
    state.output.detail("Pool Hotkey", {"Address": result})


@lending_group.command("get-global-params")
@network_option
@click.pass_context
def get_global_params(ctx: click.Context, network: str | None) -> None:
    """View current global pool parameters."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_global_params(kp))
    state.output.detail("Global Params", result)


@lending_group.command("get-market-params")
@click.option("--market-id", type=int, required=True, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def get_market_params(ctx: click.Context, market_id: int, network: str | None) -> None:
    """View interest-rate parameters for a market."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_market_params(kp, market_id))
    if result is None:
        state.output.info(f"No market params configured for market {market_id}")
        return
    state.output.detail(f"Market {market_id} Params", result)


@lending_group.command("get-alpha-params")
@click.option("--netuid", type=int, required=True, help="Subnet UID")
@network_option
@click.pass_context
def get_alpha_params(ctx: click.Context, netuid: int, network: str | None) -> None:
    """View alpha market parameters for a subnet."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_alpha_params(kp, netuid))
    if result is None:
        state.output.info(f"No alpha params configured for netuid {netuid}")
        return
    state.output.detail(f"Alpha Params (Netuid {netuid})", result)


@lending_group.command("get-maintainer")
@network_option
@click.pass_context
def get_maintainer(ctx: click.Context, network: str | None) -> None:
    """View the current pool maintainer address."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_maintainer(kp))
    state.output.detail("Maintainer", {"Address": result})


@lending_group.command("update-maintainer")
@click.option("--new-maintainer", required=True, help="New maintainer SS58 address")
@wallet_option
@network_option
@click.pass_context
def update_maintainer(
    ctx: click.Context,
    new_maintainer: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update the pool maintainer (governance-gated)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.submit(lambda c, kp: c.lending_update_maintainer(kp, new_maintainer))
    state.output.success("Maintainer updated successfully.")
