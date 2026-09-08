"""Off-chain lending-pool interest math (Python mirror of the ink! contract).

Mirrors the fixed-point accrual semantics of
``Phase2SmartContract/contracts/tusdt-lending-pool/rates.rs``
(``TusdtLendingPool::accrue_interest`` / ``compute_borrow_rate``) so the CLI
can project debt growth without a chain round-trip.  Everything here is pure
integer arithmetic at the same scales the contract uses:

* ratios (borrow index, utilization, rates) at ``RATIO_SCALE = 1e18``,
* balances (debt, cash, scaled debt) in raw underlying integer units,
* timestamps in milliseconds.

Accrual rules replicated exactly (``rates.rs::accrue_interest``):

1. ``total_debt == 0`` — no accrual happens at all.
2. Live debt but less than one full elapsed hour (``dt_hours == 0``) — no
   accrual; the sub-hour remainder is preserved on-chain, so a projection
   over a partial hour is also a no-op.
3. Whole-hours-only charging: ``dt_hours = (now_ms - last_update_ms) //
   MS_PER_HOUR`` and only that many whole hours of growth are applied
   (no hour-beginning ``+1``).
4. Every fixed-point multiply is floored at ``1e18``, including each step of
   the exponentiation (square-and-multiply) used for the growth factor.

Besides the borrow side (:func:`project_debt`) the module also mirrors the
supply side (:func:`project_exchange_rate`): the exchange rate grows by
``(1 + supply_hourly) ** dt_hours`` where ``supply_hourly = borrow_annual ×
utilization × (1 − reserve_factor) // 8760``, so the CLI can show the rate a
supply/withdraw transaction actually applies before the next on-chain
accrual.

The projection is advisory: the on-chain state advances only when
``accrue_interest`` runs, so the numbers here can differ from a later
on-chain read by timing and by the pool's own cash (which the CLI estimates
from ``MarketState`` — see ``commands/lending.py``).
"""

from __future__ import annotations

RATIO_SCALE = 10**18
MS_PER_HOUR = 3_600_000
HOURS_PER_YEAR = 8760


def bps_to_ratio_inner(bps: int) -> int:
    """Convert a basis-points integer (10_000 = 100%) to a 1e18 ratio inner."""
    return bps * 10**14


def derive_cash(
    total_supplied: int,
    exchange_rate_inner: int,
    total_debt: int,
    reserve_accrued: int,
) -> int:
    """Derive a market's physical cash from the MarketState balance-sheet
    invariant ``cash = total_supplied × exchange_rate / 1e18 − total_debt +
    reserve_accrued`` (all in underlying units, the ratio at 1e18).

    This matches the contract's ``market_cash`` exactly when the pool's books
    balance. Root-subnet-staked TAO is implicitly included: staking moves free
    balance into ``staked_tao`` and the invariant is defined on their sum
    (``market_cash(0) = env().balance() + staked_tao``), so the derived cash
    must never be replaced by a free-balance-only read. Returns ``0`` for a
    negative result (drifted/odd state).
    """
    cash = total_supplied * exchange_rate_inner // RATIO_SCALE - total_debt + reserve_accrued
    return max(cash, 0)


def face_from_ltao(ltoken_amount: int, exchange_rate_inner: int) -> int:
    """Face (underlying) value of an lToken balance — ``floor(ltoken × ER / 1e18)``.

    The contract redeems ``ltoken_amount`` for exactly this many underlying
    rao (its ``compute_redeem_amount`` floors at 1e18), so this is the TAO /
    TUSDT a user actually receives when burning ``ltoken_amount`` lTokens.
    """
    return ltoken_amount * exchange_rate_inner // RATIO_SCALE


def pow_fixed(base_inner: int, exp: int) -> int:
    """Fixed-point integer power, flooring at ``RATIO_SCALE`` every step.

    Mirrors ink!'s ``Ratio::checked_pow`` (square-and-multiply), which
    re-normalises ``inner / 1e18`` after every multiplication.
    """
    result = RATIO_SCALE
    base = base_inner
    while exp > 0:
        if exp & 1:
            result = result * base // RATIO_SCALE
        base = base * base // RATIO_SCALE
        exp >>= 1
    return result


def compute_borrow_rate(
    base_inner: int,
    slope1_inner: int,
    slope2_inner: int,
    optimal_inner: int,
    utilization_inner: int,
) -> int:
    """Annual borrow rate (1e18 ratio) from the piecewise interest-rate curve.

    Replicates ``rates.rs::compute_borrow_rate``:

    * utilization 0        -> base rate
    * utilization <= optimal -> base + slope1 * utilization / optimal
    * utilization > optimal -> base + slope1 + slope2 * (util - optimal) / (1 - optimal)

    The contract returns ``Error::ArithmeticError`` when a branch divides by
    zero (``optimal == 0`` below-optimal, or ``optimal == 1e18`` above); we
    raise ``ValueError`` instead — callers must catch it and fall back.
    """
    if utilization_inner == 0:
        return base_inner
    if utilization_inner <= optimal_inner:
        if optimal_inner == 0:
            raise ValueError("optimal utilization is zero (ArithmeticError in contract)")
        fraction = utilization_inner * RATIO_SCALE // optimal_inner
        term = slope1_inner * fraction // RATIO_SCALE
        return base_inner + term
    range_inner = RATIO_SCALE - optimal_inner
    if range_inner == 0:
        raise ValueError("optimal utilization is 100% (ArithmeticError in contract)")
    excess = utilization_inner - optimal_inner
    fraction = excess * RATIO_SCALE // range_inner
    term = slope2_inner * fraction // RATIO_SCALE
    return base_inner + slope1_inner + term


def project_debt(
    scaled_debt: int,
    borrow_index_inner: int,
    total_debt: int,
    cash: int,
    params: dict[str, int],
    last_update_ms: int,
    now_ms: int,
) -> dict[str, int]:
    """Project a user's debt after whole-hour interest accrual (off-chain).

    ``params`` carries the market's interest-rate curve as 1e18 ratio inners
    under the keys ``base`` / ``slope1`` / ``slope2`` / ``optimal`` (the
    full snake_case field names are also accepted defensively).

    Returns a dict with keys ``dt_hours``, ``projected_index_inner``,
    ``projected_debt``, ``current_debt``, ``interest_delta``,
    ``utilization_inner`` and ``annual_rate_inner``.

    No-accrual cases (``total_debt == 0``, or less than one whole hour
    elapsed — including a negative ``now_ms - last_update_ms``, which is
    clamped to zero) return ``projected == current`` and an
    ``interest_delta`` of zero; ``dt_hours`` is reported as ``max(0,
    dt_hours)`` in every case.
    """
    dt_ms = now_ms - last_update_ms
    if dt_ms < 0:
        dt_ms = 0
    dt_hours = dt_ms // MS_PER_HOUR

    utilization_inner = 0
    if total_debt > 0:
        total_liquidity = total_debt + cash
        if total_liquidity > 0:
            utilization_inner = total_debt * RATIO_SCALE // total_liquidity

    base_inner = _param(params, "base", "base_rate")
    slope1_inner = _param(params, "slope1")
    slope2_inner = _param(params, "slope2")
    optimal_inner = _param(params, "optimal", "optimal_utilization")
    annual_rate_inner = compute_borrow_rate(
        base_inner,
        slope1_inner,
        slope2_inner,
        optimal_inner,
        utilization_inner,
    )

    current_debt = scaled_debt * borrow_index_inner // RATIO_SCALE
    projected_index_inner = borrow_index_inner
    projected_debt = current_debt
    interest_delta = 0

    if total_debt > 0 and dt_hours > 0:
        # Whole-hours-only charging (rates.rs): hourly = annual // 8760,
        # growth = 1 + hourly, index *= growth^dt_hours with every fixed-
        # point multiply floored at 1e18.
        hourly_inner = annual_rate_inner // HOURS_PER_YEAR
        growth_inner = RATIO_SCALE + hourly_inner
        projected_index_inner = borrow_index_inner * pow_fixed(growth_inner, dt_hours) // RATIO_SCALE
        projected_debt = scaled_debt * projected_index_inner // RATIO_SCALE
        interest_delta = projected_debt - current_debt

    return {
        "dt_hours": max(0, dt_hours),
        "projected_index_inner": projected_index_inner,
        "projected_debt": projected_debt,
        "current_debt": current_debt,
        "interest_delta": interest_delta,
        "utilization_inner": utilization_inner,
        "annual_rate_inner": annual_rate_inner,
    }


def project_exchange_rate(
    exchange_rate_inner: int,
    total_debt: int,
    cash: int,
    params: dict[str, int],
    last_update_ms: int,
    now_ms: int,
) -> dict[str, int]:
    """Project a market's exchange rate after whole-hour interest accrual.

    Mirrors the supplier-side path of ``rates.rs::accrue_interest``: the rate
    grows by ``(1 + supply_hourly) ** dt_hours`` where ``supply_hourly =
    borrow_annual × utilization × (1 − reserve_factor) // 8760`` — every
    fixed-point multiply floored at 1e18, whole hours only (same no-accrual
    rules as :func:`project_debt`: ``total_debt == 0`` or ``dt_hours == 0``
    return the stored rate unchanged).

    ``params`` carries the rate curve as 1e18 inners under ``base`` /
    ``slope1`` / ``slope2`` / ``optimal`` plus ``reserve_factor`` (the full
    snake_case field names are also accepted defensively).  Callers build it
    from the BPS config returned by ``get_market_params`` via
    :func:`bps_to_ratio_inner` — a missing ``reserve_factor`` is treated as
    0% (the whole borrow-interest share grows the rate).

    Returns a dict with keys ``dt_hours``, ``utilization_inner``,
    ``annual_borrow_rate_inner``, ``annual_supply_rate_inner``,
    ``hourly_supply_rate_inner`` and ``projected_exchange_rate_inner``.
    """
    dt_ms = now_ms - last_update_ms
    if dt_ms < 0:
        dt_ms = 0
    dt_hours = dt_ms // MS_PER_HOUR

    utilization_inner = 0
    if total_debt > 0:
        total_liquidity = total_debt + cash
        if total_liquidity > 0:
            utilization_inner = total_debt * RATIO_SCALE // total_liquidity

    base_inner = _param(params, "base", "base_rate")
    slope1_inner = _param(params, "slope1")
    slope2_inner = _param(params, "slope2")
    optimal_inner = _param(params, "optimal", "optimal_utilization")
    reserve_factor_inner = _param(params, "reserve_factor", "reserveFactorInner")

    annual_borrow_inner = compute_borrow_rate(
        base_inner,
        slope1_inner,
        slope2_inner,
        optimal_inner,
        utilization_inner,
    )
    # rates.rs:79-82 — supply_rate_annual = borrow × utilization ×
    # (1 − reserve_factor), each fixed-point multiply floored at 1e18.
    one_minus_rf = RATIO_SCALE - reserve_factor_inner
    with_util = annual_borrow_inner * utilization_inner // RATIO_SCALE
    annual_supply_inner = with_util * one_minus_rf // RATIO_SCALE
    # rates.rs:83-85 — hourly = annual // 8760 (raw-integer division).
    hourly_supply_inner = annual_supply_inner // HOURS_PER_YEAR

    projected_er = exchange_rate_inner
    if total_debt > 0 and dt_hours > 0:
        # rates.rs:89-91/105-106 — growth = (1 + hourly)^dt_hours
        # (square-and-multiply, truncating) then rate × growth / 1e18.
        growth_inner = RATIO_SCALE + hourly_supply_inner
        projected_er = exchange_rate_inner * pow_fixed(growth_inner, dt_hours) // RATIO_SCALE

    return {
        "dt_hours": max(0, dt_hours),
        "utilization_inner": utilization_inner,
        "annual_borrow_rate_inner": annual_borrow_inner,
        "annual_supply_rate_inner": annual_supply_inner,
        "hourly_supply_rate_inner": hourly_supply_inner,
        "projected_exchange_rate_inner": projected_er,
    }


def _param(params: dict[str, int], *names: str) -> int:
    """Return the first present key of ``names`` from ``params`` (0 default).

    Rate-curve dicts can carry short names (``base`` / ``optimal``) built by
    this module's callers or the full decoded snake_case field names
    (``base_rate`` / ``optimal_utilization``); accept both defensively.
    """
    for name in names:
        if name in params:
            return params[name]
    return 0
