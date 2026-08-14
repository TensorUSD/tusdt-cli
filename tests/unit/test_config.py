"""Tests for tusdt_cli.config."""

from __future__ import annotations

import json

from tusdt_cli import config
from tusdt_cli.config import (
    DEFAULT_CONFIG,
    NETWORKS,
    apply_network_override,
    load_config,
    save_config,
)


class TestNetworks:
    def test_finney_and_testnet_present(self):
        assert "finney" in NETWORKS
        assert "testnet" in NETWORKS

    def test_each_network_has_required_keys(self):
        required = [
            "rpc",
            "vault_address",
            "token_address",
            "auction_address",
            "oracle_address",
            "governance_address",
            "treasury_address",
            "election_address",
        ]
        for name, net in NETWORKS.items():
            for key in required:
                assert key in net, f"{name} missing {key}"

    def test_each_network_has_addresses(self):
        for name, net in NETWORKS.items():
            for key in [
                "vault_address",
                "token_address",
                "auction_address",
                "oracle_address",
                "governance_address",
                "treasury_address",
                "election_address",
            ]:
                assert net[key], f"{name}.{key} is empty"


class TestDefaultConfig:
    def test_default_config_has_all_keys(self):
        expected_keys = [
            "network",
            "rpc",
            "vault_address",
            "token_address",
            "auction_address",
            "oracle_address",
            "governance_address",
            "treasury_address",
            "election_address",
            "lending_address",
            "vault_metadata",
            "token_metadata",
            "auction_metadata",
            "oracle_metadata",
            "governance_metadata",
            "treasury_metadata",
            "election_metadata",
            "lending_metadata",
            "signer",
            "signer_address",
            "wallet_name",
            "wallet_hotkey",
            "wallet_path",
            "decimals",
        ]
        for key in expected_keys:
            assert key in DEFAULT_CONFIG, f"Missing {key} in DEFAULT_CONFIG"

    def test_default_network_is_finney(self):
        assert DEFAULT_CONFIG["network"] == "finney"

    def test_default_decimals_is_9(self):
        assert DEFAULT_CONFIG["decimals"] == 9


class TestApplyNetworkOverride:
    def test_none_returns_unchanged(self):
        cfg = {"rpc": "custom", "vault_address": "0x1"}
        result = apply_network_override(cfg, None)
        assert result["rpc"] == "custom"

    def test_known_network_applies_preset(self):
        cfg = {"rpc": "custom"}
        result = apply_network_override(cfg, "testnet")
        assert result["rpc"] == NETWORKS["testnet"]["rpc"]
        assert result["network"] == "testnet"
        assert result["vault_address"] == NETWORKS["testnet"]["vault_address"]

    def test_unknown_network_returns_unchanged(self):
        cfg = {"rpc": "custom"}
        result = apply_network_override(cfg, "nonexistent")
        assert result["rpc"] == "custom"

    def test_original_not_mutated(self):
        cfg = {"rpc": "custom"}
        apply_network_override(cfg, "testnet")
        assert cfg["rpc"] == "custom"


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_config_file):
        """When no config file exists, returns defaults."""
        # Ensure file doesn't exist
        if tmp_config_file.exists():
            tmp_config_file.unlink()
        cfg = load_config()
        assert cfg["network"] == "finney"
        assert cfg["decimals"] == 9

    def test_merges_saved_values(self, tmp_config_file):
        saved = {"decimals": 6}
        tmp_config_file.write_text(json.dumps(saved))
        cfg = load_config()
        assert cfg["decimals"] == 6
        # Defaults still present
        assert cfg["network"] == "finney"

    def test_network_override_applies_presets(self, tmp_config_file):
        if tmp_config_file.exists():
            tmp_config_file.unlink()
        cfg = load_config(network="testnet")
        assert cfg["rpc"] == NETWORKS["testnet"]["rpc"]
        assert cfg["vault_address"] == NETWORKS["testnet"]["vault_address"]

    def test_saved_values_beat_network_presets(self, tmp_config_file):
        """User-explicit saved values override network preset values."""
        saved = {"rpc": "wss://my-custom-node:443"}
        tmp_config_file.write_text(json.dumps(saved))
        cfg = load_config(network="testnet")
        assert cfg["rpc"] == "wss://my-custom-node:443"

    def test_stale_abi_paths_removed(self, tmp_config_file):
        """Stale ABI paths are stripped from saved config, so defaults are used."""
        saved = {
            "vault_metadata": "/nonexistent/path/tusdt_vault.json",
            "decimals": 3,
        }
        tmp_config_file.write_text(json.dumps(saved))
        cfg = load_config()
        # The stale path is gone; the bundled default path is used instead.
        assert cfg["vault_metadata"] != "/nonexistent/path/tusdt_vault.json"
        assert cfg["decimals"] == 3  # good keys preserved

    def test_corrupt_json_falls_back_to_defaults(self, tmp_config_file):
        tmp_config_file.write_text("not valid json{{{")
        cfg = load_config()
        assert cfg["network"] == "finney"

    def test_explorer_urls_defined(self):
        assert "finney" in config.EXPLORER_URLS
        assert "testnet" in config.EXPLORER_URLS


class TestSaveConfig:
    def test_writes_valid_json(self, tmp_config_file):
        save_config({"network": "testnet"})
        assert tmp_config_file.exists()
        data = json.loads(tmp_config_file.read_text())
        assert data["network"] == "testnet"

    def test_creates_config_dir(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "new-config-dir"
        monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(config, "CONFIG_FILE", config_dir / "config.json")
        save_config({"network": "finney"})
        assert config_dir.exists()
        assert (config_dir / "config.json").exists()
