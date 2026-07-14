"""Tests for tusdt_cli.utils — balance conversion, contract unwrappers, helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tusdt_cli.utils import (
    ContractError,
    format_balance,
    parse_balance,
    unwrap_option,
    unwrap_plain,
    unwrap_query,
    unwrap_result,
    viewpallet_url,
)


class TestFormatBalance:
    def test_zero(self):
        assert format_balance(0) == "0"
        assert format_balance(0, decimals=6) == "0"

    def test_whole_number(self):
        assert format_balance(1_000_000_000, decimals=9) == "1"
        assert format_balance(5_000_000_000, decimals=9) == "5"

    def test_fractional(self):
        assert format_balance(1_500_000_000, decimals=9) == "1.5"
        assert format_balance(100_000_000, decimals=9) == "0.1"

    def test_small_fraction(self):
        assert format_balance(1, decimals=9) == "0.000000001"
        assert format_balance(123, decimals=9) == "0.000000123"

    def test_trailing_zeros_stripped(self):
        assert format_balance(1_500_000_000, decimals=9) == "1.5"
        assert format_balance(1_000_000_000, decimals=9) == "1"

    def test_custom_decimals(self):
        assert format_balance(150, decimals=2) == "1.5"
        assert format_balance(100, decimals=2) == "1"


class TestParseBalance:
    def test_whole(self):
        assert parse_balance("1") == 1_000_000_000
        assert parse_balance("5") == 5_000_000_000

    def test_decimal(self):
        assert parse_balance("1.5") == 1_500_000_000
        assert parse_balance("0.1") == 100_000_000

    def test_small_decimal(self):
        assert parse_balance("0.000000001") == 1
        assert parse_balance("0.000000123") == 123

    def test_strips_whitespace(self):
        assert parse_balance(" 1.5 ") == 1_500_000_000

    def test_custom_decimals(self):
        assert parse_balance("1.5", decimals=2) == 150

    def test_round_trip(self):
        values = ["1", "1.5", "0.1", "0.000000001", "1000", "0"]
        for v in values:
            assert format_balance(parse_balance(v)) == v


class TestViewpalletUrl:
    def test_finney(self):
        url = viewpallet_url("0xabc123", network="finney")
        assert "viewpallet.com" in url
        assert "0xabc123" in url

    def test_testnet(self):
        url = viewpallet_url("0xdef456", network="testnet")
        assert "dev.viewpallet.com" in url
        assert "0xdef456" in url


class TestUnwrapQuery:
    def test_ok(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", {"value": 42})
        assert unwrap_query(mock) == {"value": 42}

    def test_not_ok(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Err", MagicMock(value="failed"))
        with pytest.raises(ContractError, match="Contract execution failed"):
            unwrap_query(mock)

    def test_none_data(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = None
        with pytest.raises(ContractError, match="Empty contract result"):
            unwrap_query(mock)


class TestUnwrapOption:
    def test_some(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", MagicMock(value={"key": "val"}))
        assert unwrap_option(mock) == {"key": "val"}

    def test_none(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", None)
        assert unwrap_option(mock) is None

    def test_dict_none_variant(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", MagicMock(value={"None": ""}))
        assert unwrap_option(mock) is None


class TestUnwrapResult:
    def test_ok(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", MagicMock(value={"Ok": 42}))
        assert unwrap_result(mock) == 42

    def test_err(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", MagicMock(value={"Err": "bad"}))
        with pytest.raises(ContractError, match="Contract error"):
            unwrap_result(mock)


class TestUnwrapPlain:
    def test_plain_value(self):
        mock = MagicMock()
        mock.contract_result_data.value_object = ("Ok", MagicMock(value=42))
        assert unwrap_plain(mock) == 42
