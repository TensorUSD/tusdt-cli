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
        ["vault", "token", "auction", "oracle", "governance", "treasury", "election", "lending"],
    )
    def test_group_help(self, group, runner):
        result = runner.invoke(cli, [group, "--help"])
        assert result.exit_code == 0, f"{group} --help failed: {result.output[:200]}"

    @pytest.mark.parametrize(
        "group",
        ["vault", "token", "auction", "oracle", "governance", "treasury", "election", "lending"],
    )
    def test_group_shows_commands(self, group, runner):
        """Each group lists at least one subcommand."""
        result = runner.invoke(cli, [group, "--help"])
        assert "Commands:" in result.output


class TestVaultAlphaCommands:
    """Verify new/changed vault commands are registered."""

    @pytest.mark.parametrize(
        "command",
        [
            "create",
            "add-collateral",
            "release-collateral",
            "borrow",
            "repay",
            "info",
            "list",
            "params",
            "set-params",
            "execute-update",
            "cancel-update",
            "pending-update",
            "set-global-params",
            "execute-global-update",
            "cancel-global-update",
            "get-global-params",
            "set-approved-netuid",
            "is-approved-netuid",
            "claim-excess-alpha",
            "hotkey",
            "active-liquidation-count",
            "set-hotkey",
            "transfer-native-balance",
        ],
    )
    def test_vault_command_help(self, command, runner):
        """Each vault command shows --help."""
        result = runner.invoke(cli, ["vault", command, "--help"])
        assert result.exit_code == 0, f"vault {command} --help failed: {result.output[:200]}"

    def test_create_requires_netuid(self, runner):
        """create requires --netuid flag."""
        result = runner.invoke(cli, ["vault", "create", "--help"])
        assert "--netuid" in result.output

    def test_release_collateral_requires_dest_coldkey(self, runner):
        """release-collateral requires --dest-coldkey flag."""
        result = runner.invoke(cli, ["vault", "release-collateral", "--help"])
        assert "--dest-coldkey" in result.output


class TestGovernanceNewForwarders:
    """Verify new governance forwarder commands."""

    @pytest.mark.parametrize(
        "command",
        [
            "vault-claim-excess-alpha",
            "vault-hotkey",
            "vault-set-hotkey",
            "vault-transfer-native-balance",
            "vault-set-approved-netuid",
            "vault-set-global-params",
            "vault-cancel-global-update",
            "elect-maintainer",
            "election-set-netuid",
        ],
    )
    def test_forwarder_command_help(self, command, runner):
        result = runner.invoke(cli, ["governance", command, "--help"])
        assert result.exit_code == 0, f"governance {command} --help failed: {result.output[:200]}"


class TestTokenMinterCommands:
    """Verify new token minter admin commands."""

    @pytest.mark.parametrize(
        "command",
        ["set-controller", "add-minter", "remove-minter", "is-minter"],
    )
    def test_minter_command_help(self, command, runner):
        result = runner.invoke(cli, ["token", command, "--help"])
        assert result.exit_code == 0, f"token {command} --help failed: {result.output[:200]}"


class TestAuctionActiveCount:
    """Verify new auction active-count command."""

    def test_active_count_help(self, runner):
        result = runner.invoke(cli, ["auction", "active-count", "--help"])
        assert result.exit_code == 0
