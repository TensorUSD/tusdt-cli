"""Configuration management for TUSDT CLI.

Stores and loads settings from ~/.tusdt-cli/config.json.
"""

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".tusdt-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ABI files bundled inside the package at src/tusdt_cli/abi/
_ABI_DIR = Path(__file__).resolve().parent / "abi"

NETWORKS: dict[str, dict[str, str]] = {
    "finney": {
        "rpc": "wss://entrypoint-finney.opentensor.ai:443",
        "vault_address": "5GxJw8kTpapdHRW5KUXQLVDpXMMnA61mbzS6nF6jWsEeWExV",
        "token_address": "5CJ4HtCPdoMfdNUk6B7vZ348XryeXAnb5BmDNGejob1FziNH",
        "auction_address": "5HipAvNRiuh9mpTKztPLTvwyYkhzuSqxe1wsUy1fbRwbZUbQ",
        "oracle_address": "5Dfz8xgQoCsaWWrDxjeCuKB8R6AtYymWZDDDAe2q7NE8tL8A",
        "governance_address": "5CEPPTnB2YtEv7Cf8TXrFkdr6BPkDAUhDJbiT38t1A1g83g5",
        "treasury_address": "5FcjwHj8NkAMbPzkqzYweeC7KW4LffLW7KEKAR62Dx2cft2f",
    },
    "testnet": {
        "rpc": "wss://test.finney.opentensor.ai:443",
        "vault_address": "5H8nuGvHJdNXuSWtquddcGQDgAvK4vEvXmvKwU6o4cCmvfPu",
        "token_address": "5DXy5zJ28txkfLQH8uUQSjQWJQQL5hrMVY5Wiv6BwLZX66Gi",
        "auction_address": "5CqXrT8gkRx7EZrMRQjzAY6xUzPAk96GByM4N8wP889y5rju",
        "oracle_address": "5FAwRfw6HcHFqrLEPbqy73UR1HGBxesS3oAtsFe6Z1P8ZKbS",
        "governance_address": "5EvsJM6hkZruvVAAxnYLCtEkkBiWLWfA8fFC51kgwh5o2rYN",
        "treasury_address": "5EhtUDuQnvNfWpjkakwr7prdZCgubQCgsCSSctZDFgtw1fNv",
    },
}
DEFAULT_CONFIG: dict[str, Any] = {
    "network": "finney",
    "rpc": NETWORKS["finney"]["rpc"],
    "vault_address": NETWORKS["finney"]["vault_address"],
    "token_address": NETWORKS["finney"]["token_address"],
    "auction_address": NETWORKS["finney"]["auction_address"],
    "oracle_address": NETWORKS["finney"]["oracle_address"],
    "governance_address": NETWORKS["finney"]["governance_address"],
    "treasury_address": NETWORKS["finney"]["treasury_address"],
    "vault_metadata": str(_ABI_DIR / "tusdt_vault.json"),
    "token_metadata": str(_ABI_DIR / "tusdt_erc20.json"),
    "auction_metadata": str(_ABI_DIR / "tusdt_auction.json"),
    "oracle_metadata": str(_ABI_DIR / "tusdt_oracle.json"),
    "governance_metadata": str(_ABI_DIR / "tusdt_governance.json"),
    "treasury_metadata": str(_ABI_DIR / "tusdt_treasury.json"),
    "signer": None,
    "wallet_name": None,
    "wallet_hotkey": "default",
    "wallet_path": str(Path.home() / ".bittensor" / "wallets"),
    "decimals": 9,
    "access_mode": "user",
}


def ensure_config_dir() -> None:
    """Create the config directory if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def apply_network_override(config: dict[str, Any], network: str | None) -> dict[str, Any]:
    """Return a copy of *config* with network preset values applied.

    When *network* is given (e.g. ``"testnet"``), the RPC endpoint and
    contract addresses are replaced with the values from ``NETWORKS``.
    The original dict is not mutated.
    """
    if not network:
        return config
    net = network.lower()
    if net not in NETWORKS:
        return config
    merged = dict(config)
    merged.update(NETWORKS[net])
    merged["network"] = net
    return merged


def load_config(network: str | None = None) -> dict[str, Any]:
    """Load configuration from disk, filling defaults for missing keys.

    When *network* is given the returned config is overlaid with that
    network's preset (RPC + contract addresses).
    """
    config = dict(DEFAULT_CONFIG)
    saved: dict[str, Any] = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            # Strip stale ABI paths so new bundled defaults are used after upgrades.
            for key in (
                "vault_metadata",
                "token_metadata",
                "auction_metadata",
                "oracle_metadata",
                "governance_metadata",
                "treasury_metadata",
            ):
                if key in saved and not Path(saved[key]).exists():
                    del saved[key]
            config.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    effective_network = network or config.get("network")
    config = apply_network_override(config, effective_network)
    # Saved values take priority over network presets so that explicit
    # 'config set' changes (e.g. --oracle) are never silently overwritten.
    config.update(saved)
    # The effective network name is always authoritative.
    if effective_network:
        config["network"] = effective_network
    return config


def save_config(config: dict[str, Any]) -> None:
    """Persist configuration to disk."""
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def update_config(**kwargs: Any) -> dict[str, Any]:
    """Update specific configuration values and save."""
    config = load_config()
    for key, value in kwargs.items():
        if value is not None:
            config[key] = value
    save_config(config)
    return config
