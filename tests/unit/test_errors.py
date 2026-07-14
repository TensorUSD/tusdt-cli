"""Tests for tusdt_cli.errors."""

from __future__ import annotations

from tusdt_cli.errors import REMEDIATION, ErrorCode, TUSDTError


class TestErrorCode:
    def test_all_codes_are_strings(self):
        for code in ErrorCode:
            assert isinstance(code.value, str)

    def test_all_codes_have_remediation(self):
        for code in ErrorCode:
            assert code in REMEDIATION, f"Missing REMEDIATION for {code}"

    def test_codes_are_lowercase_snake(self):
        for code in ErrorCode:
            assert code.value == code.value.lower()
            assert " " not in code.value


class TestTUSDTError:
    def test_default_code_is_unknown(self):
        err = TUSDTError("something happened")
        assert err.code == ErrorCode.UNKNOWN

    def test_explicit_code(self):
        err = TUSDTError("cannot connect", code=ErrorCode.CONNECTION_FAILED)
        assert err.code == ErrorCode.CONNECTION_FAILED

    def test_message_preserved(self):
        err = TUSDTError("test message", code=ErrorCode.INVALID_ARGUMENT)
        assert str(err) == "test message"
        assert err.message == "test message"

    def test_is_exception(self):
        err = TUSDTError("boom")
        assert isinstance(err, Exception)
