"""Unit tests for the off-chain lending interest math (rates.rs mirror)."""

from __future__ import annotations

from typing import ClassVar

import pytest

from tusdt_cli.lending_interest import (
    HOURS_PER_YEAR,
    MS_PER_HOUR,
    RATIO_SCALE,
    bps_to_ratio_inner,
    compute_borrow_rate,
    derive_cash,
    face_from_ltao,
    pow_fixed,
    project_debt,
    project_exchange_rate,
)

# Live pool exchange-rate inner observed on-chain (pinned, not approximate):
# 1 lTAO ≈ 1.002816870398849427 TAO.  All math below is exact integer
# arithmetic at 1e18 scale.
ER_INNER = 1_002_816_870_398_849_427

PARAMS = {"base": 0, "slope1": 0, "slope2": 0, "optimal": 8 * 10**17}


class TestFaceFromLtao:
    def test_par_rate_face_equals_ltoken(self):
        # ER 1.0: supply of 2_000_000_000 rao mints 2_000_000_000 lTAO.
        assert face_from_ltao(2_000_000_000, RATIO_SCALE) == 2_000_000_000

    def test_live_rate_pin_redeems_999999999(self):
        # Real-chain pin: burning 997_191_042 lTAO at the live rate redeems
        # 999_999_999 rao (~1.0 TAO) — NOT 997_191_042 rao (0.9972 TAO).
        assert face_from_ltao(997_191_042, ER_INNER) == 999_999_999

    def test_zero_ltoken(self):
        assert face_from_ltao(0, ER_INNER) == 0


class TestBpsToRatioInner:
    def test_one_hundred_percent(self):
        assert bps_to_ratio_inner(10_000) == RATIO_SCALE

    def test_eighty_percent(self):
        assert bps_to_ratio_inner(8_000) == 8 * 10**17

    def test_zero(self):
        assert bps_to_ratio_inner(0) == 0


class TestComputeBorrowRate:
    def test_zero_utilization_returns_base(self):
        base = 10**16
        assert compute_borrow_rate(base, 4 * 10**16, 96 * 10**16, 8 * 10**17, 0) == base

    def test_below_optimal(self):
        # util 40% < optimal 80%: base(0) + slope1(4%) * 40/80 = 2%
        rate = compute_borrow_rate(0, 4 * 10**16, 96 * 10**16, 8 * 10**17, 4 * 10**17)
        assert rate == 2 * 10**16

    def test_above_optimal(self):
        # util 90% > optimal 80%:
        # base(1%) + slope1(4%) + slope2(96%) * (90-80)/(100-80) = 1+4+48 = 53%
        rate = compute_borrow_rate(10**16, 4 * 10**16, 96 * 10**16, 8 * 10**17, 9 * 10**17)
        assert rate == 53 * 10**16

    def test_at_optimal(self):
        # util == optimal: base + slope1 * 1.0 = 5%
        rate = compute_borrow_rate(10**16, 4 * 10**16, 96 * 10**16, 8 * 10**17, 8 * 10**17)
        assert rate == 5 * 10**16

    def test_optimal_100_percent_with_excess_utilization_raises(self):
        # Mirrors the contract's ArithmeticError on the zero range (1 - optimal).
        with pytest.raises(ValueError, match="optimal utilization is 100%"):
            compute_borrow_rate(0, 0, 0, RATIO_SCALE, 2 * RATIO_SCALE)

    def test_zero_optimal_with_positive_utilization_does_not_raise(self):
        # util > optimal == 0 falls into the above-optimal branch whose range
        # is 1e18 — same arithmetic the Rust contract performs.
        rate = compute_borrow_rate(0, 10**16, 10**16, 0, 5 * 10**17)
        assert rate == 10**16 + 5 * 10**15


class TestPowFixed:
    def test_zero_exponent_is_one(self):
        assert pow_fixed(RATIO_SCALE + 123, 0) == RATIO_SCALE

    def test_square_of_small_increment(self):
        # (1 + 2e-18)^2 floored at 1e18 per step == 1 + 4e-18
        assert pow_fixed(RATIO_SCALE + 2, 2) == RATIO_SCALE + 4

    def test_cube_of_unit_increment(self):
        assert pow_fixed(RATIO_SCALE + 1, 3) == RATIO_SCALE + 3


class TestProjectDebtNoAccrual:
    def test_sub_hour_elapsed_is_noop(self):
        result = project_debt(
            scaled_debt=RATIO_SCALE,
            borrow_index_inner=RATIO_SCALE,
            total_debt=10**9,
            cash=10**9,
            params=PARAMS,
            last_update_ms=0,
            now_ms=MS_PER_HOUR - 1,
        )
        assert result["dt_hours"] == 0
        assert result["projected_index_inner"] == RATIO_SCALE
        assert result["projected_debt"] == result["current_debt"] == RATIO_SCALE
        assert result["interest_delta"] == 0

    def test_negative_dt_is_clamped(self):
        # now < last_update (clock skew) must not accrue or go negative.
        result = project_debt(
            scaled_debt=RATIO_SCALE,
            borrow_index_inner=RATIO_SCALE,
            total_debt=10**9,
            cash=10**9,
            params=PARAMS,
            last_update_ms=5_000_000,
            now_ms=4_000_000,
        )
        assert result["dt_hours"] == 0
        assert result["projected_debt"] == result["current_debt"]
        assert result["interest_delta"] == 0

    def test_zero_total_debt_is_noop(self):
        # No debt → no accrual even after many hours (rates.rs rule 1).
        result = project_debt(
            scaled_debt=RATIO_SCALE,
            borrow_index_inner=3 * RATIO_SCALE // 2,
            total_debt=0,
            cash=10**9,
            params={"base": 10**16, "slope1": 0, "slope2": 0, "optimal": 8 * 10**17},
            last_update_ms=0,
            now_ms=100 * MS_PER_HOUR,
        )
        assert result["dt_hours"] == 100
        assert result["projected_index_inner"] == 3 * RATIO_SCALE // 2
        assert result["projected_debt"] == result["current_debt"]
        assert result["interest_delta"] == 0


class TestProjectDebtAccrual:
    def test_one_hour_at_small_rate_grows(self):
        # 8.76% annual → hourly 1e-5 (1e13 inner). 2.0 debt accrues 2e-5.
        base_inner = 87600 * 10**12
        result = project_debt(
            scaled_debt=2 * RATIO_SCALE,
            borrow_index_inner=RATIO_SCALE,
            total_debt=10**9,
            cash=10**9,
            params={"base": base_inner, "slope1": 0, "slope2": 0, "optimal": 8 * 10**17},
            last_update_ms=0,
            now_ms=MS_PER_HOUR,
        )
        assert result["dt_hours"] == 1
        assert result["annual_rate_inner"] == base_inner
        assert result["utilization_inner"] == 5 * 10**17
        assert result["projected_index_inner"] == RATIO_SCALE + base_inner // HOURS_PER_YEAR
        assert result["interest_delta"] == 2 * (base_inner // HOURS_PER_YEAR)
        assert result["projected_debt"] == result["current_debt"] + result["interest_delta"]

    def test_whole_hour_flooring_ignores_sub_hour_remainder(self):
        # 2.5h elapsed charges exactly 2 hours (rates.rs: no +1 hour).
        # The second-order growth term survives per-step flooring, exactly as
        # the contract's checked_pow computes it.
        base_inner = 87600 * 10**12
        hourly = base_inner // HOURS_PER_YEAR
        result = project_debt(
            scaled_debt=RATIO_SCALE,
            borrow_index_inner=RATIO_SCALE,
            total_debt=10**9,
            cash=10**9,
            params={"base": base_inner, "slope1": 0, "slope2": 0, "optimal": 8 * 10**17},
            last_update_ms=0,
            now_ms=2 * MS_PER_HOUR + MS_PER_HOUR // 2,
        )
        assert result["dt_hours"] == 2
        assert result["projected_index_inner"] == RATIO_SCALE + 2 * hourly + hourly * hourly // RATIO_SCALE
        assert result["interest_delta"] == 2 * hourly + hourly * hourly // RATIO_SCALE

    def test_dust_flooring_two_rao_debt_stays_two(self):
        # Pinned dust-flooring behavior: with 2 raw units of debt and an
        # hourly rate of 1 (1e-18 inner), one hour of growth floors back to
        # exactly 2 — mirroring mul_value(growth, 2) in the contract.
        result = project_debt(
            scaled_debt=2,
            borrow_index_inner=RATIO_SCALE,
            total_debt=2,
            cash=2,
            params={"base": HOURS_PER_YEAR, "slope1": 0, "slope2": 0, "optimal": RATIO_SCALE},
            last_update_ms=0,
            now_ms=MS_PER_HOUR,
        )
        assert result["dt_hours"] == 1
        assert result["annual_rate_inner"] == HOURS_PER_YEAR
        # The index does advance by 1 inner (exact division), but the user's
        # 2-raw-unit debt floors back to 2 — the pinned dust behavior.
        assert result["projected_index_inner"] == RATIO_SCALE + 1
        assert result["projected_debt"] == 2
        assert result["interest_delta"] == 0


class TestDeriveCash:
    def test_invariant_matches_physical_cash_with_staked_tao(self):
        # Balance-sheet invariant: cash = supplier_face + reserve − debt.
        # Root-subnet-staked TAO is implicitly included — the contract's
        # market_cash(0) = env().balance() + staked_tao, and the invariant is
        # defined on that sum. Free 10 TAO + staked 40 TAO = 50 TAO cash with
        # supplier face 100, debt 50, reserve 0.
        cash = derive_cash(
            total_supplied=100 * 10**9,
            exchange_rate_inner=RATIO_SCALE,
            total_debt=50 * 10**9,
            reserve_accrued=0,
        )
        assert cash == 50 * 10**9

    def test_reserve_is_included(self):
        cash = derive_cash(
            total_supplied=100 * 10**9,
            exchange_rate_inner=RATIO_SCALE,
            total_debt=50 * 10**9,
            reserve_accrued=3 * 10**9,
        )
        assert cash == 53 * 10**9

    def test_negative_result_clamps_to_zero(self):
        assert derive_cash(10 * 10**9, RATIO_SCALE, 50 * 10**9, 0) == 0


class TestProjectExchangeRate:
    # Doc lifecycle params (docs/calculations/lending-pool.md): util 40%,
    # borrow 2%/yr, supply 0.64%/yr, reserve factor 20% — all 1e18 inners.
    PARAMS: ClassVar[dict[str, int]] = {
        "base": 0,
        "slope1": 4 * 10**16,
        "slope2": 96 * 10**16,
        "optimal": 8 * 10**17,
        "reserve_factor": 2 * 10**17,
    }

    def test_720h_lifecycle_pin(self):
        # 720 whole hours at util 40% (debt 800 TAO / cash 1200 TAO). The
        # expected inner is produced by this module's own truncating pow_fixed
        # — the same value the dApp's TypeScript mirror pins; the doc's 18-dp
        # decimal 1.000526165581675953 is a rendering artifact (its own ΔER
        # ...849 figure agrees with ...849).
        result = project_exchange_rate(
            exchange_rate_inner=RATIO_SCALE,
            total_debt=800 * 10**9,
            cash=1_200 * 10**9,
            params=self.PARAMS,
            last_update_ms=0,
            now_ms=720 * MS_PER_HOUR,
        )
        assert result["dt_hours"] == 720
        assert result["utilization_inner"] == 400_000_000_000_000_000  # 40%
        assert result["annual_borrow_rate_inner"] == 20_000_000_000_000_000  # 2%
        assert result["annual_supply_rate_inner"] == 6_400_000_000_000_000  # 0.64%
        assert result["hourly_supply_rate_inner"] == 730_593_607_305  # doc :130
        assert result["projected_exchange_rate_inner"] == 1_000_526_165_581_675_849

    def test_no_debt_returns_stored_rate(self):
        result = project_exchange_rate(
            exchange_rate_inner=RATIO_SCALE,
            total_debt=0,
            cash=1_200 * 10**9,
            params=self.PARAMS,
            last_update_ms=0,
            now_ms=720 * MS_PER_HOUR,
        )
        assert result["dt_hours"] == 720
        assert result["projected_exchange_rate_inner"] == RATIO_SCALE

    def test_sub_hour_elapsed_is_no_op(self):
        # 30 minutes < one whole hour — the contract preserves the sub-hour
        # remainder and accrues nothing; the projection must match.
        result = project_exchange_rate(
            exchange_rate_inner=RATIO_SCALE,
            total_debt=800 * 10**9,
            cash=1_200 * 10**9,
            params=self.PARAMS,
            last_update_ms=1_700_000_000_000,
            now_ms=1_700_000_000_000 + MS_PER_HOUR // 2,
        )
        assert result["dt_hours"] == 0
        assert result["projected_exchange_rate_inner"] == RATIO_SCALE

    def test_zero_cash_full_utilization_grows_rate(self):
        # No cash with live debt → 100% utilization → slope2 zone (borrow
        # annual = 4% + 96% = 100%); the rate must grow.
        result = project_exchange_rate(
            exchange_rate_inner=RATIO_SCALE,
            total_debt=800 * 10**9,
            cash=0,
            params=self.PARAMS,
            last_update_ms=0,
            now_ms=MS_PER_HOUR,
        )
        assert result["utilization_inner"] == RATIO_SCALE  # 100%
        assert result["annual_borrow_rate_inner"] == RATIO_SCALE  # 100%/yr
        assert result["dt_hours"] == 1
        assert result["projected_exchange_rate_inner"] > RATIO_SCALE

    def test_missing_reserve_factor_defaults_to_zero(self):
        # A params dict without reserve_factor is treated as 0% reserve — the
        # whole borrow-interest share grows the exchange rate.
        result = project_exchange_rate(
            exchange_rate_inner=RATIO_SCALE,
            total_debt=800 * 10**9,
            cash=1_200 * 10**9,
            params={"base": 0, "slope1": 4 * 10**16, "slope2": 96 * 10**16, "optimal": 8 * 10**17},
            last_update_ms=0,
            now_ms=MS_PER_HOUR,
        )
        # supply annual = borrow 2% × util 40% = 0.8% (no rf cut) →
        # hourly = 0.008 × 1e18 // 8760.
        assert result["annual_supply_rate_inner"] == 8_000_000_000_000_000
        assert result["hourly_supply_rate_inner"] == 913_242_009_132

    def test_negative_clock_is_clamped_no_op(self):
        result = project_exchange_rate(
            exchange_rate_inner=RATIO_SCALE,
            total_debt=800 * 10**9,
            cash=1_200 * 10**9,
            params=self.PARAMS,
            last_update_ms=1_700_000_000_000,
            now_ms=1_000_000_000_000,
        )
        assert result["dt_hours"] == 0
        assert result["projected_exchange_rate_inner"] == RATIO_SCALE
