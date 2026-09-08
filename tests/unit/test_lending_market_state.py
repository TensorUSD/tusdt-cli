"""Unit tests for the market-state display helper (lTAO → face TAO scaling).

Pins the real-chain incident: total_supplied 997_191_042 lTAO at exchange
rate 1_002_816_870_398_849_427 must be shown as 999_999_999 rao face
(~1.0 TAO), never as the raw lTAO count.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tusdt_cli.cli import cli
from tusdt_cli.commands.lending import _market_state_details
from tusdt_cli.context import CLIContext

ER_INNER = 1_002_816_870_398_849_427


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestMarketStateDetails:
    def test_live_rate_scales_total_supplied_to_face(self):
        details = _market_state_details(
            {"total_supplied": 997_191_042, "exchange_rate": ER_INNER, "total_debt": 0},
            0,
        )
        assert details["market"] == "0 (TAO)"
        assert details["total_supplied (lTAO, raw)"] == 997_191_042
        assert details["total_supplied (lTAO)"] == "0.997191042"
        # The fix: face supply is ~1.0 TAO, not 0.9972 TAO (the raw lTAO).
        assert details["total supplied (face TAO)"] == "0.999999999"
        assert details["total supplied (face TAO, raw)"] == 999_999_999
        # Unrelated fields pass through untouched; raw lTAO/rate keys are not
        # re-emitted under their bare names.
        assert details["total_debt"] == 0
        assert "total_supplied" not in details
        assert "exchange_rate" not in details
        assert details["exchange_rate (1e18 inner)"] == ER_INNER
        assert details["exchange_rate (TAO per lTAO)"] == "1.002816870398849427"

    def test_tusdt_market_uses_tusdt_labels(self):
        details = _market_state_details(
            {"total_supplied": 997_191_042, "exchange_rate": ER_INNER},
            1,
        )
        assert details["market"] == "1 (TUSDT)"
        assert details["total_supplied (lTUSDT, raw)"] == 997_191_042
        assert details["total supplied (face TUSDT)"] == "0.999999999"

    def test_par_rate_face_row_equals_raw(self):
        details = _market_state_details({"total_supplied": 2_000_000_000, "exchange_rate": 10**18}, 0)
        assert details["total supplied (face TAO)"] == "2"
        assert details["total supplied (face TAO, raw)"] == 2_000_000_000

    def test_missing_exchange_rate_marks_face_unavailable(self):
        details = _market_state_details({"total_supplied": 997_191_042}, 0)
        assert details["total supplied (face TAO)"] == "n/a (no exchange rate in state)"

    def test_unknown_market_id_uses_generic_labels(self):
        details = _market_state_details(
            {"total_supplied": 997_191_042, "exchange_rate": ER_INNER},
            7,
        )
        assert details["market"] == "7 (underlying)"
        assert details["total_supplied (lToken, raw)"] == 997_191_042
        assert details["total supplied (face underlying)"] == "0.999999999"

    def test_non_dict_payload_passes_through_raw(self):
        assert _market_state_details(["not", "a", "dict"], 0) == {"Result": ["not", "a", "dict"]}

    def test_camel_case_aliases_are_normalised_away(self):
        # _dict_field tolerates camelCase aliases from drifted ABIs.
        details = _market_state_details(
            {"totalSupplied": 997_191_042, "exchangeRate": ER_INNER, "totalDebt": 0},
            0,
        )
        assert details["total_supplied (lTAO, raw)"] == 997_191_042
        assert details["total supplied (face TAO)"] == "0.999999999"
        assert "totalSupplied" not in details
        assert "exchangeRate" not in details


class TestMarketStateCommand:
    @patch.object(CLIContext, "run_read")
    @patch("tusdt_cli.context.load_config")
    def test_command_renders_face_row(self, mock_load, mock_run_read, runner):
        mock_load.return_value = {
            "decimals": 9,
            "network": "finney",
            "rpc": "ws://127.0.0.1:9944",
            "lending_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        }
        mock_run_read.return_value = {"total_supplied": 997_191_042, "exchange_rate": ER_INNER}
        result = runner.invoke(cli, ["lending", "market-state", "--market-id", "0"])
        assert result.exit_code == 0
        assert "total supplied (face TAO)" in result.output
        assert "0.999999999" in result.output


# Exchange-rate projection test fixtures: the 720-hour lifecycle from
# test_lending_interest (util 40%: debt 800 TAO, derived cash 1200 TAO).
PROJ_STATE = {
    "total_supplied": 2_000 * 10**9,  # 2000 lTAO at par ER = 2000 TAO face
    "exchange_rate": 10**18,
    "total_debt": 800 * 10**9,
    "reserve_accrued": 0,
    "last_update": 1_700_000_000_000,
}
PROJ_PARAMS = {
    "base_rate": 0,
    "slope1": 400,  # 4% in BPS
    "slope2": 9600,  # 96% in BPS
    "optimal_utilization": 8000,  # 80% in BPS
    "reserve_factor": 2000,  # 20% in BPS
}
PROJ_TIMES = (1_700_000_000_000, 1_700_000_000_000)
PROJ_NOW = 1_700_000_000_000 + 720 * 3_600_000
PROJ_ER = 1_000_526_165_581_675_849  # projected ER after 720 h (pinned in tests)


class TestMarketStateDetailsProjection:
    def test_projection_replaces_rate_and_face_rows(self):
        details = _market_state_details(
            {"total_supplied": 997_191_042, "exchange_rate": ER_INNER, "total_debt": 1},
            0,
            projection={
                "projected_exchange_rate_inner": PROJ_ER,
                "dt_hours": 720,
                "projected_to_utc": "2026-09-08 00:00:00 UTC",
            },
        )
        # The primary rows show the projected (current) rate; the stored rate
        # stays visible under an explicit row with the pending hours.
        assert details["exchange_rate (1e18 inner)"] == PROJ_ER
        assert details["exchange_rate stored (1e18 inner)"] == ER_INNER
        assert details["accrual pending (hours)"] == 720
        face = 997_191_042 * PROJ_ER // 10**18
        assert details["total supplied (face TAO, raw)"] == face
        assert details["exchange_rate (TAO per lTAO)"] == "1.000526165581675849"

    def test_projection_equal_to_stored_adds_no_rows(self):
        # No unaccrued hours (or no debt): projection == stored — the output
        # must be byte-identical to the pre-projection shape.
        details = _market_state_details(
            {"total_supplied": 997_191_042, "exchange_rate": ER_INNER, "total_debt": 1},
            0,
            projection={"projected_exchange_rate_inner": ER_INNER, "dt_hours": 0},
        )
        assert details["exchange_rate (1e18 inner)"] == ER_INNER
        assert "exchange_rate stored (1e18 inner)" not in details
        assert "accrual pending (hours)" not in details


class TestMarketStateCommandProjection:
    @patch.object(CLIContext, "run_read")
    @patch("tusdt_cli.context.load_config")
    def test_command_shows_projected_rate_with_pending_hours(self, mock_load, mock_run_read, runner):
        mock_load.return_value = {
            "decimals": 9,
            "network": "finney",
            "rpc": "ws://127.0.0.1:9944",
            "lending_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        }
        # Read order: market-state, market params, accrual times, chain clock.
        mock_run_read.side_effect = [PROJ_STATE, PROJ_PARAMS, PROJ_TIMES, PROJ_NOW]
        result = runner.invoke(cli, ["lending", "market-state", "--market-id", "0"])
        assert result.exit_code == 0
        assert "accrual pending (hours)" in result.output
        assert "1.000526165581675849" in result.output  # projected per-lTAO
        assert "exchange_rate stored (1e18 inner)" in result.output


class TestExchangeRateCommandProjection:
    @patch.object(CLIContext, "run_read")
    @patch("tusdt_cli.context.load_config")
    def test_command_enriches_stored_rate_with_projection(self, mock_load, mock_run_read, runner):
        mock_load.return_value = {
            "decimals": 9,
            "network": "finney",
            "rpc": "ws://127.0.0.1:9944",
            "lending_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        }
        # Read order: exchange-rate, market-state, params, accrual times, clock.
        mock_run_read.side_effect = [10**18, PROJ_STATE, PROJ_PARAMS, PROJ_TIMES, PROJ_NOW]
        result = runner.invoke(cli, ["lending", "exchange-rate", "--market-id", "0"])
        assert result.exit_code == 0
        # The projected rate is the raw 1e18 inner (no decimal formatting in
        # this command — that lives in market-state's per-lToken row).
        assert "1000526165581675849" in result.output
        assert "Accrual pending (hours)" in result.output

    @patch.object(CLIContext, "run_read")
    @patch("tusdt_cli.context.load_config")
    def test_command_stays_legacy_without_projection_inputs(self, mock_load, mock_run_read, runner):
        mock_load.return_value = {
            "decimals": 9,
            "network": "finney",
            "rpc": "ws://127.0.0.1:9944",
            "lending_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        }
        # Market state without debt → projection skipped; reads stop early.
        mock_run_read.side_effect = [10**18, {"exchange_rate": ER_INNER, "total_debt": 0}]
        result = runner.invoke(cli, ["lending", "exchange-rate", "--market-id", "0"])
        assert result.exit_code == 0
        assert "Accrual pending (hours)" not in result.output
