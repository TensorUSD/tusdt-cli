"""Lending pool CLI commands."""

import time
from datetime import datetime, timezone
from typing import Any

import click

from tusdt_cli import lending_interest
from tusdt_cli.context import CLIContext
from tusdt_cli.globals import network_option, wallet_option
from tusdt_cli.utils import (
    HelpfulGroup,
    ModeAwareGroup,
    format_balance,
    parse_balance,
)
from tusdt_cli.wallet import get_reader_keypair, resolve_signer_address

# Commands hidden unless the saved config has access_mode = "dev".
_ADVANCED: set[str] = {"root-stake-config", "sweep"}


@click.group("lending", cls=ModeAwareGroup, advanced=_ADVANCED)
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
    """Repay a TUSDT loan. Requires prior token approval.

    Before submitting, the signer's TUSDT allowance to the lending pool is
    verified and the command aborts (with an `approve` hint) when it cannot
    cover the repayment.  The check runs before submission, so --dry-run
    validates it too.  When the signer address cannot be derived (encrypted
    wallets) the check is skipped with a warning instead of blocking.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    raw_amount = parse_balance(amount, cfg.get("decimals", 9))

    # Allowance pre-check: refuse to submit a repayment the pool's
    # transfer_from cannot collect.  The spender is the lending pool
    # contract, resolved from the same config key client.py uses for its
    # lazy `lending` property so it can never drift from the real target.
    spender = cfg.get("lending_address")
    if spender:
        owner = resolve_signer_address(cfg)
        if owner is None:
            state.output.info(
                "Signer address unavailable (encrypted wallet?) — TUSDT allowance could not be verified."
            )
        else:
            kp = get_reader_keypair(cfg)
            allowance = state.run_read(lambda c: c.allowance(kp, owner, spender))
            if allowance is None or allowance < raw_amount:
                raise click.ClickException(
                    f"TUSDT allowance {allowance} is below the {raw_amount} needed to repay — "
                    f"approve first: tusdt token approve {spender} {amount} --wallet-name <name>"
                )
    else:
        state.output.info("Lending pool address not configured — skipping TUSDT allowance pre-check.")

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
@wallet_option
@network_option
@click.pass_context
def liquidate(
    ctx: click.Context,
    borrower: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Liquidate an underwater borrower (full seizure).

    The borrower's FULL debt on both markets is repaid — TAO via the
    attached native value and TUSDT via transfer_from (requires prior
    token approval) — and ALL of the borrower's alpha collateral is
    seized, minus the platform's liquidation fee.

    Before submitting, the borrower's debt on both markets and the
    TUSDT/TAO oracle price are read so the liquidator sees the exact
    payment amounts.  When the borrower is underwater the contract
    clamps the seized collateral, so submitting with the full debt
    values is safe.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()

    # Read the borrower's full debt on both markets plus the TUSDT/TAO
    # oracle price (single client, three contract reads).
    kp = get_reader_keypair(cfg)
    debt_tao, debt_tusdt, price_data = state.run_read(
        lambda c: (
            c.lending_get_user_debt(kp, 0, borrower),
            c.lending_get_user_debt(kp, 1, borrower),
            c.get_latest_price(kp),
        )
    )

    # Full-seizure model: the liquidator pays the borrower's whole debt on
    # both markets.  TAO is paid as native value; TUSDT is pulled via
    # transfer_from.  If the borrower is underwater the contract clamps the
    # collateral seized, so the full debt values are always safe to submit.
    payment_tao = int(debt_tao or 0)
    payment_tusdt = int(debt_tusdt or 0)

    raw_price = 0
    if isinstance(price_data, dict):
        raw_price = int(price_data.get("price", 0) or 0)
    # Oracle price is TUSDT per TAO as a 1e18 ratio.
    tusdt_per_tao = raw_price / 10**18 if raw_price else 0.0
    # TUSDT → TAO equivalent: TUSDT_rao × 1e18 / price (never inverted).
    tusdt_in_tao = int(payment_tusdt * 10**18 // raw_price) if raw_price else 0

    if payment_tao == 0 and payment_tusdt == 0:
        state.output.warning("Borrower has no outstanding debt on either market.")

    state.output.info("Liquidation summary (full seizure):")
    state.output.detail(
        "Liquidation",
        {
            "Borrower": borrower,
            "TAO payment (native value)": format_balance(payment_tao),
            "TUSDT payment (transfer_from)": format_balance(payment_tusdt),
            "TUSDT payment (≈ TAO)": (format_balance(tusdt_in_tao) if raw_price else "n/a (no oracle price)"),
            "Oracle price (TUSDT per TAO)": (f"{tusdt_per_tao:.10f}" if raw_price else "n/a"),
        },
    )
    state.output.info(
        "Fee note: the platform retains its liquidation fee from the seized "
        "alpha (see set-alpha-params --liquidation-fee)."
    )

    state.submit(
        lambda c, kp: c.lending_liquidate(
            kp,
            borrower,
            value=payment_tao,
        )
    )
    state.output.success(
        f"Liquidation submitted successfully! Native TAO value attached: {format_balance(payment_tao)}."
    )


# ======================================================================
# Permissionless Claims
# ======================================================================


@lending_group.command("claim-alpha-excess")
@click.option("--netuid", required=True, type=int, help="Subnet netuid")
@wallet_option
@network_option
@click.pass_context
def claim_alpha_excess(ctx: click.Context, netuid: int, wallet_name: str | None, network: str | None) -> None:
    """Claim excess alpha staking for a netuid (permissionless).

    Unstakes the full excess (available stake minus booked principal) and
    sends the TAO directly to the treasury.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_claim_alpha_excess(kp, netuid))
    state.output.success("Alpha excess claimed and sent to the treasury!")


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
@click.option(
    "--liquidation-fee",
    type=int,
    default=None,
    help="Liquidation fee in BPS (e.g. 500 = 5% of seized alpha taken by the platform)",
)
@click.option("--supply-cap", type=str, default=None, help="Supply cap (0 = unlimited)")
@wallet_option
@network_option
@click.pass_context
def set_alpha_params(
    ctx: click.Context,
    netuid: int,
    collateral_factor: int | None,
    liquidation_threshold: int | None,
    liquidation_fee: int | None,
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
            "liquidation_fee": liquidation_fee
            if liquidation_fee is not None
            else existing.get("liquidation_fee", 0),
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
# Interest Accrual
# ======================================================================


@lending_group.command("accrue-market-interest")
@wallet_option
@network_option
@click.pass_context
def accrue_market_interest(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Accrue interest for both debt markets (permissionless).

    Refreshes each market's borrow index, exchange rate, and reserve against
    the time elapsed since its last accrual. Markets with no debt or with less
    than one full hour elapsed accrue nothing.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.make_config()
    state.submit(lambda c, kp: c.lending_accrue_market_interest(kp))
    state.output.success("Interest accrued for both debt markets!")


# ======================================================================
# Queries / Getters
# ======================================================================


@lending_group.command("market-state")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def market_state(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show market state (supply, debt, rates, reserve).

    MarketState tracks supply in lToken units, so alongside the raw lToken
    count the command shows the face (underlying) supply it represents at
    the current exchange rate — raw lTAO counts are never presented as TAO.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_market_state(kp, market_id))
    state.output.detail("Market State", _market_state_details(result, market_id))


def _market_state_details(result: Any, market_id: int) -> dict[str, Any]:
    """Curate a decoded MarketState for display, adding face-scaled supply.

    ``MarketState.total_supplied`` is denominated in lToken (scaled) units —
    the face value owed to suppliers is ``total_supplied × exchange_rate``
    (see the contract's MarketState docs).  The raw dict passes through
    key-for-key except the supply/rate fields, which are re-emitted with
    explicit unit labels, and a derived face row is added so a raw lTAO
    count is never mistaken for plain TAO.
    """
    if not isinstance(result, dict):
        # Unexpected payload shape (not a decoded struct) — keep it raw.
        return {"Result": result}
    if market_id == 0:
        asset, ltoken = "TAO", "lTAO"
    elif market_id == 1:
        asset, ltoken = "TUSDT", "lTUSDT"
    else:
        asset, ltoken = "underlying", "lToken"
    total_supplied = _dict_field(result, "total_supplied", "totalSupplied")
    exchange_rate_inner = _dict_field(result, "exchange_rate", "exchangeRate")
    has_supply = isinstance(total_supplied, int)
    has_rate = isinstance(exchange_rate_inner, int) and exchange_rate_inner > 0

    details: dict[str, Any] = {"market": f"{market_id} ({asset})"}
    for key, value in result.items():
        # The supply/rate fields are re-emitted below with explicit units.
        if key.replace("_", "").lower() in ("totalsupplied", "exchangerate"):
            continue
        details[key] = value
    if has_supply:
        details[f"total_supplied ({ltoken}, raw)"] = total_supplied
        details[f"total_supplied ({ltoken})"] = format_balance(total_supplied)
    if has_supply and has_rate:
        face = lending_interest.face_from_ltao(total_supplied, exchange_rate_inner)
        details[f"total supplied (face {asset})"] = format_balance(face)
        details[f"total supplied (face {asset}, raw)"] = face
        details["exchange_rate (1e18 inner)"] = exchange_rate_inner
        details[f"exchange_rate ({asset} per {ltoken})"] = format_balance(exchange_rate_inner, 18)
    elif has_supply:
        details[f"total supplied (face {asset})"] = "n/a (no exchange rate in state)"
    return details


@lending_group.command("market-deficit")
@click.option("--market-id", required=True, type=int, help="Market ID: 0 for TAO, 1 for TUSDT")
@network_option
@click.pass_context
def market_deficit(ctx: click.Context, market_id: int, network: str | None) -> None:
    """Show a market's frozen bad-debt deficit (face units of the market's asset).

    A deficit is the residual of a write-off during liquidation, booked when
    the borrower's collateral was exhausted. None means nothing is booked.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_market_deficit(kp, market_id))
    if result is None:
        state.output.info(f"No deficit booked for market {market_id}")
        return
    state.output.detail("Market Deficit", {"Result": result})


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
    tracking.  For debt markets (0 or 1) the output additionally carries an
    off-chain projection of the debt including unaccrued interest, computed
    by replaying the pool's whole-hour accrual math locally (see
    ``tusdt_cli.lending_interest``); the projection is silently omitted when
    any required state read fails.
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
    details: dict[str, object] = {
        "Debt (on-chain)": debt,
        "Principal": principal,
        "Interest (on-chain)": debt - principal,
    }
    if market_id in (0, 1):
        projection = _project_user_debt(state, kp, market_id, user)
        if projection is not None:
            details.update(projection)
    state.output.detail("User Debt Details", details)


def _dict_field(data: Any, *names: str, default: Any = None) -> Any:
    """Read the first present key of ``names`` from a decoded contract dict.

    substrate-interface decodes ink! structs to snake_case dicts, but key
    shapes can drift across deployed ABIs — accept each snake_case name and
    a camelCase alias defensively.
    """
    if isinstance(data, dict):
        for name in names:
            if name in data:
                return data[name]
    return default


def _project_user_debt(state: CLIContext, kp: Any, market_id: int, user: str) -> dict[str, Any] | None:
    """Project the user's debt including unaccrued interest (off-chain).

    Replays the lending pool's whole-hour accrual math
    (``lending_interest.project_debt``, mirroring ``rates.rs``) from on-chain
    state: the position's scaled debt, the market borrow index, total debt
    and last accrual time.  Pool cash — not exposed as a message — is derived
    from the MarketState invariant ``cash = total_supplied * exchange_rate -
    total_debt + reserve_accrued`` (exact up to per-accrual exchange-rate
    floor dust).  Returns the extra detail rows, or ``None`` when any read
    fails or a required value is missing so the caller silently falls back to
    the on-chain-only output.  Never raises.
    """
    try:
        position = state.run_read(lambda c: c.lending_get_position(kp, market_id, user))
        scaled_debt = _dict_field(position, "scaled_debt")
        borrow_index_inner = state.run_read(lambda c: c.lending_get_borrow_index(kp, market_id))
        market_state = state.run_read(lambda c: c.lending_get_market_state(kp, market_id))
        params = state.run_read(lambda c: c.lending_get_market_params(kp, market_id))
        if scaled_debt is None or borrow_index_inner is None:
            return None
        total_debt = _dict_field(market_state, "total_debt")
        if total_debt is None:
            return None

        cash = 0
        if total_debt > 0:
            total_supplied = _dict_field(market_state, "total_supplied")
            exchange_rate = _dict_field(market_state, "exchange_rate")
            reserve_accrued = _dict_field(market_state, "reserve_accrued")
            if total_supplied is None or exchange_rate is None or reserve_accrued is None:
                return None
            cash = lending_interest.derive_cash(
                total_supplied,
                exchange_rate,
                total_debt,
                reserve_accrued,
            )

        # Last accrual time: prefer the dedicated message's tuple element;
        # fall back to the market state's last_update when it is missing/zero.
        accrual_times = state.run_read(lambda c: c.lending_get_last_interest_accrual_times(kp))
        last_update_ms: Any = None
        if isinstance(accrual_times, (list, tuple)) and len(accrual_times) > market_id:
            last_update_ms = accrual_times[market_id]
        if not last_update_ms:
            last_update_ms = _dict_field(market_state, "last_update")
        if last_update_ms is None:
            return None
        if last_update_ms == 0 and scaled_debt:
            # last_update == 0 means "never accrued" — impossible for a
            # consistent market with live debt (borrow accrues first and
            # stamps the clock). Bail out rather than projecting interest
            # from the Unix epoch.
            return None

        # Chain clock (Timestamp pallet, ms) — the same clock the contract's
        # block_timestamp() reads. The local wall clock is only a fallback: a
        # skewed client clock shifts dt_hours by a whole hour at boundaries.
        now_ms = state.run_read(lambda c: c.lending_get_chain_timestamp(kp))
        if not now_ms:
            now_ms = int(time.time() * 1000)

        params_inner = {
            "base": lending_interest.bps_to_ratio_inner(_dict_field(params, "base_rate", default=0)),
            "slope1": lending_interest.bps_to_ratio_inner(_dict_field(params, "slope1", default=0)),
            "slope2": lending_interest.bps_to_ratio_inner(_dict_field(params, "slope2", default=0)),
            "optimal": lending_interest.bps_to_ratio_inner(
                _dict_field(params, "optimal_utilization", default=0)
            ),
        }
        projection = lending_interest.project_debt(
            scaled_debt,
            borrow_index_inner,
            total_debt,
            cash,
            params_inner,
            last_update_ms,
            now_ms,
        )
        projected_to = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return {
            "Projected Debt (incl. unaccrued interest)": projection["projected_debt"],
            "Projected Interest": projection["interest_delta"],
            "Projected to (UTC)": projected_to,
        }
    except Exception:
        # The projection is advisory: any failure (missing state, an
        # impossible rate-curve branch, unexpected shapes) falls back to the
        # on-chain-only output instead of breaking the command.
        return None


@lending_group.command("last-interest-accrual")
@network_option
@click.pass_context
def last_interest_accrual(ctx: click.Context, network: str | None) -> None:
    """Show the last interest-accrual timestamps for both debt markets.

    Timestamps are block timestamps in milliseconds; a zero value means the
    market has never accrued interest.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_last_interest_accrual_times(kp))
    if result is None:
        state.output.detail("Last Interest Accrual", {"Result": None})
        return
    ms0, ms1 = result
    details: dict[str, str] = {}
    for market_label, ms in (("Market 0 (TAO)", ms0), ("Market 1 (TUSDT)", ms1)):
        if ms == 0:
            details[market_label] = "0 ms (never accrued)"
        else:
            utc = datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            details[market_label] = f"{ms} ms ({utc})"
    state.output.detail("Last Interest Accrual", details)


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


# ======================================================================
# Idle-TAO root staking
# ======================================================================


@lending_group.command("tao-staked")
@network_option
@click.pass_context
def tao_staked(ctx: click.Context, network: str | None) -> None:
    """Show the booked TAO currently staked on the root subnet (netuid 0)."""
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_tao_staked(kp))
    decimals = cfg.get("decimals", 9)
    state.output.detail(
        "TAO Staked (Root Subnet)",
        {
            "Raw (rao)": result,
            "TAO": format_balance(result, decimals),
        },
    )


@lending_group.group("root-stake-config", cls=HelpfulGroup, invoke_without_command=True)
@network_option
@click.pass_context
def root_stake_config(ctx: click.Context, network: str | None) -> None:
    """Show the idle-TAO root-subnet staking configuration (advanced command).

    Use ``root-stake-config set`` to update it.
    """
    if ctx.invoked_subcommand is not None:
        return
    state: CLIContext = ctx.obj
    state.network = network or state.network
    cfg = state.make_config()
    kp = get_reader_keypair(cfg)
    result = state.run_read(lambda c: c.lending_get_root_stake_config(kp))
    if not isinstance(result, dict):
        state.output.detail("Root Stake Config", {"Result": result})
        return
    decimals = cfg.get("decimals", 9)
    state.output.table(
        "Root Stake Config",
        ["Root Hotkey", "Staking Enabled", "Stake Buffer", "Sweep Threshold", "Stake Floor"],
        [
            [
                result.get("root_hotkey"),
                result.get("staking_enabled"),
                format_balance(result.get("stake_buffer", 0), decimals),
                format_balance(result.get("sweep_threshold", 0), decimals),
                format_balance(result.get("stake_floor", 0), decimals),
            ]
        ],
    )


@root_stake_config.command("set")
@click.option("--hotkey", required=True, help="Pool hotkey SS58 address used for root staking")
@click.option(
    "--enabled/--no-enabled",
    "staking_enabled",
    default=None,
    required=True,
    help="Enable or disable idle-TAO staking",
)
@click.option(
    "--buffer",
    required=True,
    help="Idle TAO kept free for withdrawals (9-decimal amount, e.g. 1 = 1 TAO)",
)
@click.option(
    "--threshold",
    required=True,
    help="Extra free TAO required before a sweep stakes (9-decimal amount)",
)
@click.option(
    "--floor",
    required=True,
    help="Minimum TAO a single sweep stakes (9-decimal amount)",
)
@wallet_option
@network_option
@click.pass_context
def root_stake_config_set(
    ctx: click.Context,
    hotkey: str,
    staking_enabled: bool | None,
    buffer: str,
    threshold: str,
    floor: str,
    wallet_name: str | None,
    network: str | None,
) -> None:
    """Update the idle-TAO root-subnet staking configuration (governance-gated).

    The contract enforces ``stake_floor >= 2_000_000`` rao and
    ``stake_buffer >= stake_floor``.  Rotating the hotkey while TAO is
    staked fully unstakes the pool's root position first.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    cfg = state.make_config()
    decimals = cfg.get("decimals", 9)
    raw_buffer = parse_balance(buffer, decimals)
    raw_threshold = parse_balance(threshold, decimals)
    raw_floor = parse_balance(floor, decimals)
    state.submit(
        lambda c, kp: c.lending_set_root_stake_config(
            kp, hotkey, bool(staking_enabled), raw_buffer, raw_threshold, raw_floor
        )
    )
    state.output.success("Root stake config updated successfully.")


@lending_group.command("sweep")
@wallet_option
@network_option
@click.pass_context
def sweep(ctx: click.Context, wallet_name: str | None, network: str | None) -> None:
    """Stake excess idle TAO into the root subnet (permissionless keeper call).

    Advanced command.  No-op when staking is disabled, the pool is paused,
    the excess is below the stake floor, or a sweep already ran this block.
    """
    state: CLIContext = ctx.obj
    state.network = network or state.network
    state.wallet_name = wallet_name or state.wallet_name
    state.submit(lambda c, kp: c.lending_sweep(kp))
    state.output.success("Sweep submitted successfully.")
