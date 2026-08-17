"""Unit tests for the off-chain lending interest math (rates.rs mirror)."""

from __future__ import annotations

import pytest

from tusdt_cli.lending_interest import (
    HOURS_PER_YEAR,
    MS_PER_HOUR,
    RATIO_SCALE,
    bps_to_ratio_inner,
    compute_borrow_rate,
    pow_fixed,
    project_debt,
)

PARAMS = {"base": 0, "slope1": 0, "slope2": 0, "optimal": 8 * 10**17}


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
