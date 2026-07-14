"""Shared test fixtures for tusdt-cli tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_wallet_dir(fixtures_dir: Path) -> Path:
    """Path to a sample wallet directory for filesystem wallet tests."""
    return fixtures_dir / "sample_wallet"


@pytest.fixture
def sample_config_path(fixtures_dir: Path) -> Path:
    """Path to sample_config.json."""
    return fixtures_dir / "sample_config.json"


@pytest.fixture
def tmp_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Patch CONFIG_FILE and CONFIG_DIR to use a temp directory."""
    from tusdt_cli import config

    config_dir = tmp_path / ".tusdt-cli"
    config_dir.mkdir()
    config_file = config_dir / "config.json"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)

    return config_file


@pytest.fixture
def tmp_wallet_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a temp wallet directory with a valid coldkeypub.txt."""
    wallet_dir = tmp_path / "wallets" / "test-wallet"
    wallet_dir.mkdir(parents=True)
    hotkey_dir = wallet_dir / "hotkeys"
    hotkey_dir.mkdir()

    # Write a minimal coldkeypub.txt (Alice's well-known SS58)
    coldkeypub = {
        "ss58Address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "publicKey": "0xd43593c715fdd31c61141abd04a99fd6822c8558854ccde39a5684e7a56da27d",
    }
    (wallet_dir / "coldkeypub.txt").write_text(json.dumps(coldkeypub))

    # Write a minimal hotkey
    hotkey = {
        "secretPhrase": "bottom drive obey lake curtain smoke basket hold race lonely fit walk",
        "ss58Address": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
        "publicKey": "0x8eaf04151687736326c9fea17e25fc5287613693c912909cb226aa4794f26a48",
    }
    (hotkey_dir / "default").write_text(json.dumps(hotkey))

    return wallet_dir


@pytest.fixture
def clean_config(tmp_config_file):
    """Config with no saved file — returns defaults only."""
    from tusdt_cli.config import load_config

    return load_config()
