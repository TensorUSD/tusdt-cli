"""Browser extension signing for tusdt-cli.

A local bridge page talks to wallet extensions (Polkadot.js, Talisman,
SubWallet, etc.). Python clients connect over WebSocket and never see
private keys.

With ``--signer-backend extension``, the bridge starts automatically in the
background and you pick an account at the command line — no separate bridge
step.
"""

from .bridge import DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT, BridgeServer
from .client import BridgeClient, BridgeError
from .picker import pick_extension_account
from .session import ensure_bridge, start_bridge_daemon, stop_bridge_daemon
from .signer import (
    ExtensionAccount,
    ExtensionSigner,
    account_crypto_type,
    open_extension_signer,
    select_extension_account,
)

__all__ = [
    "DEFAULT_BRIDGE_HOST",
    "DEFAULT_BRIDGE_PORT",
    "BridgeClient",
    "BridgeError",
    "BridgeServer",
    "ExtensionAccount",
    "ExtensionSigner",
    "account_crypto_type",
    "ensure_bridge",
    "open_extension_signer",
    "pick_extension_account",
    "select_extension_account",
    "start_bridge_daemon",
    "stop_bridge_daemon",
]
