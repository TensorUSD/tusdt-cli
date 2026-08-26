"""Tests for tusdt_cli.client with mocked SubstrateInterface."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tusdt_cli.client import TUSDTClient
from tusdt_cli.utils import ContractError


@pytest.fixture
def minimal_config():
    """A minimal config dict for TUSDTClient construction."""
    return {
        "rpc": "ws://127.0.0.1:9944",
        "vault_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "vault_metadata": "/fake/path/tusdt_vault.json",
        "token_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "token_metadata": "/fake/path/tusdt_erc20.json",
        "auction_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "auction_metadata": "/fake/path/tusdt_auction.json",
        "oracle_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "oracle_metadata": "/fake/path/tusdt_oracle.json",
        "governance_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "governance_metadata": "/fake/path/tusdt_governance.json",
        "treasury_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "treasury_metadata": "/fake/path/tusdt_treasury.json",
        "election_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "election_metadata": "/fake/path/tusdt_election.json",
        "lending_address": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "lending_metadata": "/fake/path/tusdt_lending_pool.json",
        "network": "finney",
        "decimals": 9,
    }


class TestTUSDTClientInit:
    def test_init_does_not_connect(self, minimal_config):
        """TUSDTClient.__init__ is lazy — it does not create a SubstrateInterface."""
        client = TUSDTClient(minimal_config)
        assert client._substrate is None
        assert client._vault is None

    def test_init_stores_config(self, minimal_config):
        client = TUSDTClient(minimal_config)
        assert client.config is minimal_config


class TestTUSDTClientSubstrate:
    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    def test_substrate_property_creates_connection(self, MockMetadata, MockSubstrate, minimal_config):
        """Accessing .substrate creates a SubstrateInterface."""
        client = TUSDTClient(minimal_config)
        substrate = client.substrate
        MockSubstrate.assert_called_once()
        assert substrate is MockSubstrate.return_value

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    def test_substrate_is_cached(self, MockMetadata, MockSubstrate, minimal_config):
        """Second access to .substrate returns the cached instance."""
        client = TUSDTClient(minimal_config)
        s1 = client.substrate
        s2 = client.substrate
        assert s1 is s2
        # Only called once despite two accesses
        assert MockSubstrate.call_count == 1

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    def test_substrate_uses_u64_balance_type(self, MockMetadata, MockSubstrate, minimal_config):
        """SubstrateInterface is configured with Balance = u64."""
        client = TUSDTClient(minimal_config)
        client.substrate
        call_kwargs = MockSubstrate.call_args[1]
        assert "type_registry" in call_kwargs
        assert call_kwargs["type_registry"]["types"]["Balance"] == "u64"


class TestTUSDTClientContractProperties:
    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_vault_property_is_lazy(self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config):
        """Accessing .vault creates a ContractInstance (mocked)."""
        client = TUSDTClient(minimal_config)
        vault = client.vault
        assert vault is not None
        assert client._vault is not None
        MockContractInstance.assert_called_once()


class TestTUSDTClientRead:
    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    def test_read_calls_contract_read(self, MockMetadata, MockSubstrate, minimal_config):
        """_read calls contract.read() and returns the result."""
        client = TUSDTClient(minimal_config)
        mock_contract = MagicMock()
        mock_keypair = MagicMock()

        mock_result = MagicMock()
        mock_result.contract_result_data.value_object = ("Ok", MagicMock(value=42))
        mock_contract.read.return_value = mock_result

        result = client._read(mock_contract, mock_keypair, "get_vault", {"owner": "0x1", "vault_id": 0})
        mock_contract.read.assert_called_once()
        assert result is mock_result


class TestVaultAlphaMethods:
    """Tests for renamed/reworked vault-alpha methods."""

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_create_alpha_vault_passes_value(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """create_alpha_vault calls _exec with value kwarg for vault creation fee."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()
        mock_vault = client.vault

        client._exec = MagicMock()
        client.create_alpha_vault(mock_kp, 1000000000, 1)
        client._exec.assert_called_once_with(
            mock_vault,
            mock_kp,
            "create_alpha_vault",
            args={"amount": 1000000000, "netuid": 1},
            value=0,
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_add_alpha_collateral_not_payable(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """add_alpha_collateral passes amount as arg, not value (not payable)."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()
        mock_vault = client.vault

        client._exec = MagicMock()
        client.add_alpha_collateral(mock_kp, 0, 500000000)
        client._exec.assert_called_once_with(
            mock_vault,
            mock_kp,
            "add_alpha_collateral",
            args={"vault_id": 0, "amount": 500000000},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_release_alpha_collateral_with_dest_coldkey(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """release_alpha_collateral includes dest_coldkey in args."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()
        mock_vault = client.vault

        client._exec = MagicMock()
        client.release_alpha_collateral(
            mock_kp, 0, 500000000, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        )
        client._exec.assert_called_once_with(
            mock_vault,
            mock_kp,
            "release_alpha_collateral",
            args={
                "vault_id": 0,
                "amount": 500000000,
                "dest_coldkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            },
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_set_contract_params_with_netuid(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """set_contract_params passes netuid in args and reads current params with netuid."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()

        client._exec = MagicMock()
        client._read = MagicMock()
        client._read.return_value = MagicMock()
        unwrap_result = MagicMock(return_value={"collateral_ratio": 150, "liquidation_ratio": 120})
        with patch("tusdt_cli.client.unwrap_plain", unwrap_result):
            client.set_contract_params(mock_kp, 1, {"collateral_ratio": 200})

        client._read.assert_called_once_with(client.vault, mock_kp, "get_contract_params", args={"netuid": 1})

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_execute_contract_params_update_with_netuid(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """execute_contract_params_update passes netuid in args."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()
        mock_vault = client.vault

        client._exec = MagicMock()
        client.execute_contract_params_update(mock_kp, 1)
        client._exec.assert_called_once_with(
            mock_vault,
            mock_kp,
            "execute_contract_params_update",
            args={"netuid": 1},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_cancel_contract_params_update_with_netuid(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """cancel_contract_params_update passes netuid in args."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()
        mock_vault = client.vault

        client._exec = MagicMock()
        client.cancel_contract_params_update(mock_kp, 1)
        client._exec.assert_called_once_with(
            mock_vault,
            mock_kp,
            "cancel_contract_params_update",
            args={"netuid": 1},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_get_pending_contract_params_update_with_netuid(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
        """get_pending_contract_params_update passes netuid in args."""
        client = TUSDTClient(minimal_config)
        mock_kp = MagicMock()

        client._read = MagicMock()
        mock_result = MagicMock()
        client._read.return_value = mock_result
        with patch("tusdt_cli.client.unwrap_option", return_value=None):
            result = client.get_pending_contract_params_update(mock_kp, 1)
            assert result is None
        client._read.assert_called_once_with(
            client.vault,
            mock_kp,
            "get_pending_contract_params_update",
            args={"netuid": 1},
        )


class TestERC20MinterMethods:
    """Tests for new multi-minter ERC20 methods."""

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_add_minter(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.add_minter(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
        client._exec.assert_called_once_with(
            client.token,
            mock_kp,
            "add_minter",
            args={"minter": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_remove_minter(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.remove_minter(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
        client._exec.assert_called_once_with(
            client.token,
            mock_kp,
            "remove_minter",
            args={"minter": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_is_minter(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_plain", return_value=True):
            assert client.is_minter(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY") is True
        client._read.assert_called_once_with(
            client.token,
            mock_kp,
            "is_minter",
            args={"account": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_set_controller(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.set_controller(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
        client._exec.assert_called_once_with(
            client.token,
            mock_kp,
            "set_controller",
            args={"new_controller": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"},
        )

    # ── Hotkey getter ──

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_get_vault_hotkey(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch(
            "tusdt_cli.client.unwrap_plain", return_value="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        ):
            result = client.get_vault_hotkey(mock_kp)
            assert result == "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        client._read.assert_called_once_with(client.vault, mock_kp, "get_vault_hotkey")

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_get_active_liquidation_count(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_plain", return_value=3):
            result = client.get_active_liquidation_count(mock_kp)
            assert result == 3
        client._read.assert_called_once_with(client.vault, mock_kp, "get_active_liquidation_count")

    # ── Change hotkey ──

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_set_vault_hotkey(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.set_vault_hotkey(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", [1, 3])
        client._exec.assert_called_once_with(
            client.vault,
            mock_kp,
            "set_vault_hotkey",
            args={"new_hotkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", "netuids": [1, 3]},
        )

    # ── Transfer native to treasury ──

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_transfer_native_to_treasury(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.transfer_native_to_treasury(mock_kp)
        client._exec.assert_called_once_with(
            client.vault,
            mock_kp,
            "transfer_native_to_treasury",
            args={},
        )


class TestGovernanceNewForwarders:
    """Tests for new governance forwarder methods."""

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_vault_claim_excess_alpha(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.gov_vault_claim_excess_alpha(mock_kp, 1)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_claim_excess_alpha",
            args={"netuid": 1},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_vault_set_approved_netuid(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.gov_vault_set_approved_netuid(mock_kp, 1, True)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_set_approved_netuid",
            args={"netuid": 1, "approved": True},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_vault_set_global_params(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        config = {"transaction_fee": 30, "auction_duration_ms": 3600000}
        client.gov_vault_set_global_params(mock_kp, config)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_set_global_params",
            args={"config": config},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_vault_cancel_global_params_update(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.gov_vault_cancel_global_params_update(mock_kp)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_cancel_global_params_update",
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_elect_maintainer(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.elect_maintainer(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "elect_maintainer",
            args={"new_maintainer": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_election_set_netuid(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.election_set_netuid(mock_kp, 42)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "election_set_netuid",
            args={"netuid": 42},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_vault_set_contract_params_with_netuid(self, MockCI, MockMeta, MockSub, minimal_config):
        """gov_vault_set_contract_params passes netuid and reads with netuid."""
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()

        client._read = MagicMock()
        mock_result = MagicMock()
        client._read.return_value = mock_result
        with patch("tusdt_cli.client.unwrap_plain", return_value={"collateral_ratio": 150}):
            client.gov_vault_set_contract_params(mock_kp, 1, {"collateral_ratio": 200})
        client._read.assert_called_once_with(client.vault, mock_kp, "get_contract_params", args={"netuid": 1})

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_vault_cancel_update_with_netuid(self, MockCI, MockMeta, MockSub, minimal_config):
        """gov_vault_cancel_update passes netuid in args."""
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.gov_vault_cancel_update(mock_kp, 1)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_cancel_contract_params_update",
            args={"netuid": 1},
        )

    # ── New governance forwarders ──

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_get_vault_hotkey(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch(
            "tusdt_cli.client.unwrap_plain", return_value="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        ):
            result = client.gov_get_vault_hotkey(mock_kp)
            assert result == "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        client._read.assert_called_once_with(client.governance, mock_kp, "vault_get_hotkey")

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_set_vault_hotkey(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.gov_set_vault_hotkey(mock_kp, "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", [1, 3])
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_set_hotkey",
            args={"new_hotkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", "netuids": [1, 3]},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_gov_transfer_native_to_treasury(self, MockCI, MockMeta, MockSub, minimal_config):
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.gov_transfer_native_to_treasury(mock_kp)
        client._exec.assert_called_once_with(
            client.governance,
            mock_kp,
            "vault_transfer_native_to_treasury",
            args={},
        )


class TestLendingNewMessages:
    """Tests for the new interest-accrual lending messages."""

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_get_last_interest_accrual_times(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_get_last_interest_accrual_times reads with no args and unwraps the Option."""
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_option", return_value=[1723766400000, 1723852800000]):
            result = client.lending_get_last_interest_accrual_times(mock_kp)
            assert result == [1723766400000, 1723852800000]
        client._read.assert_called_once_with(client.lending, mock_kp, "get_last_interest_accrual_times")

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_get_last_interest_accrual_times_none(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_get_last_interest_accrual_times returns None when the Option is None."""
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_option", return_value=None):
            result = client.lending_get_last_interest_accrual_times(mock_kp)
            assert result is None
        client._read.assert_called_once_with(client.lending, mock_kp, "get_last_interest_accrual_times")

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_accrue_market_interest(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_accrue_market_interest execs with empty args (no-arg permissionless call)."""
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.lending_accrue_market_interest(mock_kp)
        client._exec.assert_called_once_with(
            client.lending,
            mock_kp,
            "accrue_market_interest",
            args={},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_set_global_params(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_set_global_params passes the config dict (incl. full_close_hf_threshold)."""
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        config = {"close_factor": 5000, "full_close_hf_threshold": 9500}
        client.lending_set_global_params(mock_kp, config)
        client._exec.assert_called_once_with(
            client.lending,
            mock_kp,
            "set_global_params",
            args={"config": config},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_get_market_deficit(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_get_market_deficit reads with market_id and unwraps the Option."""
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_option", return_value=1_250_000_000_000):
            result = client.lending_get_market_deficit(mock_kp, 1)
            assert result == 1_250_000_000_000
        client._read.assert_called_once_with(
            client.lending, mock_kp, "get_market_deficit", args={"market_id": 1}
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_get_market_deficit_none(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_get_market_deficit returns None when the Option is None (nothing booked)."""
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_option", return_value=None):
            result = client.lending_get_market_deficit(mock_kp, 0)
            assert result is None
        client._read.assert_called_once_with(
            client.lending, mock_kp, "get_market_deficit", args={"market_id": 0}
        )


class TestLendingRootStakeMessages:
    """Tests for the new idle-TAO root-stake lending messages."""

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_set_root_stake_config(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_set_root_stake_config execs with all five config args."""
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.lending_set_root_stake_config(
            mock_kp,
            root_hotkey="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            staking_enabled=True,
            stake_buffer=1_000_000_000,
            sweep_threshold=0,
            stake_floor=2_000_000,
        )
        client._exec.assert_called_once_with(
            client.lending,
            mock_kp,
            "set_root_stake_config",
            args={
                "root_hotkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
                "staking_enabled": True,
                "stake_buffer": 1_000_000_000,
                "sweep_threshold": 0,
                "stake_floor": 2_000_000,
            },
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_sweep(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_sweep execs with empty args (no-arg permissionless call)."""
        client = TUSDTClient(minimal_config)
        client._exec = MagicMock()
        mock_kp = MagicMock()
        client.lending_sweep(mock_kp)
        client._exec.assert_called_once_with(
            client.lending,
            mock_kp,
            "sweep",
            args={},
        )

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_get_tao_staked(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_get_tao_staked reads with no args and unwraps the Result."""
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        with patch("tusdt_cli.client.unwrap_result", return_value=1_000_000_000):
            result = client.lending_get_tao_staked(mock_kp)
            assert result == 1_000_000_000
        client._read.assert_called_once_with(client.lending, mock_kp, "get_tao_staked")

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    @patch("tusdt_cli.client.ContractInstance")
    def test_lending_get_root_stake_config(self, mock_ci, mock_meta, mock_sub, minimal_config):
        """lending_get_root_stake_config reads with no args and unwraps the Result."""
        client = TUSDTClient(minimal_config)
        client._read = MagicMock()
        mock_kp = MagicMock()
        fake_config = {
            "root_hotkey": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            "staking_enabled": False,
            "stake_buffer": 1_000_000_000,
            "sweep_threshold": 0,
            "stake_floor": 2_000_000,
        }
        with patch("tusdt_cli.client.unwrap_result", return_value=fake_config):
            result = client.lending_get_root_stake_config(mock_kp)
            assert result == fake_config
        client._read.assert_called_once_with(client.lending, mock_kp, "get_root_stake_config")
