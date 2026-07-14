"""Integration tests for the CLI using Click's CliRunner."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tusdt_cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestRootCLI:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "TUSDT CLI" in result.output

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_no_args_shows_help(self, runner):
        result = runner.invoke(cli)
        # Click shows usage help when invoked with no subcommand
        assert "Usage:" in result.output or "TUSDT CLI" in result.output


class TestConfigCommands:
    @patch("tusdt_cli.cli.load_config")
    def test_config_show(self, mock_load, runner):
        mock_load.return_value = {"network": "finney", "decimals": 9, "rpc": "ws://x"}
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0

    @patch("tusdt_cli.cli.save_config")
    @patch("tusdt_cli.cli.load_config")
    def test_config_set_network(self, mock_load, mock_save, runner):
        mock_load.return_value = {"network": "finney"}
        result = runner.invoke(cli, ["config", "set", "--network", "testnet"])
        assert result.exit_code == 0
        assert "Configuration updated" in result.output

    @patch("tusdt_cli.cli.save_config")
    @patch("tusdt_cli.cli.load_config")
    def test_config_set_no_options(self, mock_load, mock_save, runner):
        mock_load.return_value = {"network": "finney"}
        result = runner.invoke(cli, ["config", "set"])
        assert result.exit_code == 0
        assert "No options provided" in result.output


class TestWalletCommands:
    @patch("tusdt_cli.cli.load_config")
    def test_wallet_list_empty_directory(self, mock_load, runner, tmp_path):
        mock_load.return_value = {
            "wallet_path": str(tmp_path),
            "network": "finney",
        }
        result = runner.invoke(cli, ["wallet", "list"])
        assert result.exit_code == 0

    @patch("tusdt_cli.cli.load_config")
    def test_wallet_list_with_wallet(self, mock_load, runner, tmp_path):
        """List wallets when one exists."""
        import json

        wallet_dir = tmp_path / "test-wallet"
        wallet_dir.mkdir()
        (wallet_dir / "coldkeypub.txt").write_text(
            json.dumps({"ss58Address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"})
        )

        mock_load.return_value = {
            "wallet_path": str(tmp_path),
            "network": "finney",
        }
        result = runner.invoke(cli, ["wallet", "list"])
        assert result.exit_code == 0
        assert "test-wallet" in result.output


class TestContractGroups:
    """Verify all contract command groups are registered and have --help."""

    @pytest.mark.parametrize(
        "group",
        ["vault", "token", "auction", "oracle", "governance", "treasury", "election"],
    )
    def test_group_help(self, group, runner):
        result = runner.invoke(cli, [group, "--help"])
        assert result.exit_code == 0, f"{group} --help failed: {result.output[:200]}"

    @pytest.mark.parametrize(
        "group",
        ["vault", "token", "auction", "oracle", "governance", "treasury", "election"],
    )
    def test_group_shows_commands(self, group, runner):
        """Each group lists at least one subcommand."""
        result = runner.invoke(cli, [group, "--help"])
        assert "Commands:" in result.output
