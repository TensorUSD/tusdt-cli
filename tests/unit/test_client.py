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
    def test_substrate_property_creates_connection(
        self, MockMetadata, MockSubstrate, minimal_config
    ):
        """Accessing .substrate creates a SubstrateInterface."""
        client = TUSDTClient(minimal_config)
        substrate = client.substrate
        MockSubstrate.assert_called_once()
        assert substrate is MockSubstrate.return_value

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    def test_substrate_is_cached(
        self, MockMetadata, MockSubstrate, minimal_config
    ):
        """Second access to .substrate returns the cached instance."""
        client = TUSDTClient(minimal_config)
        s1 = client.substrate
        s2 = client.substrate
        assert s1 is s2
        # Only called once despite two accesses
        assert MockSubstrate.call_count == 1

    @patch("tusdt_cli.client.SubstrateInterface")
    @patch("tusdt_cli.client.ContractMetadata")
    def test_substrate_uses_u64_balance_type(
        self, MockMetadata, MockSubstrate, minimal_config
    ):
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
    def test_vault_property_is_lazy(
        self, MockContractInstance, MockMetadata, MockSubstrate, minimal_config
    ):
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
