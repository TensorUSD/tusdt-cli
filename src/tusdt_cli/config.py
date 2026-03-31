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
        "vault_address": "5HhJKNf7XjmppAyPeBKN5xQk6joNMWHTnEgup4msxfcKcYKp",
        "token_address": "5GGqBAYWW84wvdTeZGM68dHng1UaWTxxc4ZzFhuQXF9zqK9J",
        "auction_address": "5Cninzamn4GVi1J1St578ENyNEDrMi5hXucY7rUj1WzREgAt",
        "oracle_address": "5FqciR795agP8wEojv2TRegwN757EJURyzjDREUvzCX3cqZS",
    },
    "testnet": {
        "rpc": "wss://test.finney.opentensor.ai:443",
        "vault_address": "5HhJKNf7XjmppAyPeBKN5xQk6joNMWHTnEgup4msxfcKcYKp",
        "token_address": "5GGqBAYWW84wvdTeZGM68dHng1UaWTxxc4ZzFhuQXF9zqK9J",
        "auction_address": "5Cninzamn4GVi1J1St578ENyNEDrMi5hXucY7rUj1WzREgAt",
        "oracle_address": "5FqciR795agP8wEojv2TRegwN757EJURyzjDREUvzCX3cqZS",
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "network": "finney",
    "rpc": NETWORKS["finney"]["rpc"],
    "vault_address": NETWORKS["finney"]["vault_address"],
    "token_address": NETWORKS["finney"]["token_address"],
    "auction_address": NETWORKS["finney"]["auction_address"],
    "oracle_address": NETWORKS["finney"]["oracle_address"],
    "vault_metadata": str(_ABI_DIR / "tusdt_vault.json"),
    "token_metadata": str(_ABI_DIR / "tusdt_erc20.json"),
    "auction_metadata": str(_ABI_DIR / "tusdt_auction.json"),
    "oracle_metadata": str(_ABI_DIR / "tusdt_oracle.json"),
    "signer": None,
    "wallet_name": None,
    "wallet_hotkey": "default",
    "wallet_path": str(Path.home() / ".bittensor" / "wallets"),
    "decimals": 9,
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
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            config.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return apply_network_override(config, network)


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
