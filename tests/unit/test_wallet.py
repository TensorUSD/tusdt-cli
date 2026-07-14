"""Tests for tusdt_cli.wallet."""

from __future__ import annotations

import json

import pytest

from tusdt_cli.wallet import (
    _is_encrypted,
    _read_ss58_from_pubfile,
    get_reader_keypair,
    resolve_ss58,
)


class TestIsEncrypted:
    def test_nacl_marker(self, tmp_path):
        f = tmp_path / "encrypted_key"
        f.write_bytes(b"$NACL" + b"\x00" * 20)
        assert _is_encrypted(str(f))

    def test_json_not_encrypted(self, tmp_path):
        f = tmp_path / "json_key"
        f.write_text('{"ss58Address": "abc"}')
        assert not _is_encrypted(str(f))

    def test_empty_file_is_encrypted(self, tmp_path):
        """Empty files are not valid JSON, so they're treated as encrypted."""
        f = tmp_path / "empty_key"
        f.write_text("")
        assert _is_encrypted(str(f))


class TestReadSs58FromPubfile:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "coldkeypub.txt"
        f.write_text(
            json.dumps(
                {
                    "ss58Address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
                    "publicKey": "0xabcd",
                }
            )
        )
        addr = _read_ss58_from_pubfile(str(f))
        assert addr == "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

    def test_missing_key_returns_none(self, tmp_path):
        f = tmp_path / "coldkeypub.txt"
        f.write_text(json.dumps({"publicKey": "0xabcd"}))
        assert _read_ss58_from_pubfile(str(f)) is None

    def test_missing_file_returns_none(self):
        assert _read_ss58_from_pubfile("/nonexistent/path/coldkeypub.txt") is None

    def test_invalid_json_returns_none(self, tmp_path):
        f = tmp_path / "coldkeypub.txt"
        f.write_text("not json")
        assert _read_ss58_from_pubfile(str(f)) is None


class TestResolveSs58:
    def test_passes_through_ss58_address(self, tmp_path):
        """A raw SS58 address is returned unchanged."""
        addr = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        assert resolve_ss58(addr, str(tmp_path)) == addr

    def test_resolves_wallet_name(self, tmp_path):
        """A wallet directory name resolves to the coldkey SS58."""
        wallet_dir = tmp_path / "MyWallet"
        wallet_dir.mkdir()
        (wallet_dir / "coldkeypub.txt").write_text(
            json.dumps({"ss58Address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"})
        )
        assert resolve_ss58("MyWallet", str(tmp_path)) == "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

    def test_nonexistent_wallet_passes_through(self, tmp_path):
        """A nonexistent wallet name is returned unchanged (not an SS58 either)."""
        assert resolve_ss58("NoSuchWallet", str(tmp_path)) == "NoSuchWallet"


class TestGetReaderKeypair:
    def test_returns_alice_keypair(self):
        kp = get_reader_keypair({})
        assert kp is not None
        # Dev keypair //Alice
        assert kp.ss58_address == "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
