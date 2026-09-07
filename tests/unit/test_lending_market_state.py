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
