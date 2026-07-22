"""Extension signer that satisfies the Signer protocol.

Signs extrinsic payloads via the browser extension bridge. Never sees a
private key — the extension handles signing and the bridge relays results.

Adapted from btcli's ``bittensor/extension/signer.py``.
"""

from __future__ import annotations

from .client import BridgeClient
from .picker import ExtensionAccount, pick_extension_account


def account_crypto_type(account: dict) -> int:
    """Infer the crypto type from an extension account dict.
    ``0`` = ed25519, ``1`` = sr25519.
    """
    atype = account.get("type", account.get("crypto_type", ""))
    if isinstance(atype, str) and "sr25519" in atype.lower():
        return 1
    return 0  # default to ed25519


class ExtensionSigner:
    """A :class:`Signer` backed by a browser extension via the bridge.

    Signs extrinsics by sending the Polkadot-JS SignerPayloadJSON through
    the WebSocket bridge to the extension.
    """

    def __init__(
        self,
        client: BridgeClient,
        account: ExtensionAccount,
        crypto_type: int = 0,
    ):
        self._client = client
        self._account = account
        self._crypto_type = crypto_type

    @property
    def ss58_address(self) -> str:
        return self._account.address

    @property
    def public_key(self) -> bytes:
        # Extension accounts don't expose the raw public key through the
        # bridge; the address is sufficient for identification. If a
        # substrate-interface Keypair adapter is needed, use the
        # LedgerKeypair pattern with a dummy key.
        return bytes.fromhex(self._account.address[2:]) if self._account.address.startswith("0x") else b""

    @property
    def crypto_type(self) -> int:
        return self._crypto_type

    def sign(self, payload: bytes) -> bytes:
        """Sign raw bytes via the extension. Blocks until user approves."""
        import asyncio

        data_hex = payload.hex()
        sig_hex = asyncio.run(self._client.sign_bytes(self._account.address, data_hex))
        if sig_hex.startswith("0x"):
            sig_hex = sig_hex[2:]
        return bytes.fromhex(sig_hex)

    async def sign_extrinsic_payload(self, payload: dict) -> dict:
        """Sign a Polkadot-JS SignerPayloadJSON."""
        return await self._client.sign_extrinsic_payload(payload)

    async def close(self) -> None:
        await self._client.close()

    def __repr__(self) -> str:
        return f"ExtensionSigner({self._account.address[:12]}...)"


async def select_extension_account(
    client: BridgeClient,
    *,
    address: str | None = None,
    source: str | None = None,
) -> ExtensionAccount:
    """Connect to the bridge, list accounts, and pick one."""
    await client.connect()
    raw_accounts = await client.list_accounts()
    accounts = [
        ExtensionAccount(
            address=a.get("address", ""),
            name=a.get("name", a.get("meta", {}).get("name", "")),
            source=a.get("source", ""),
        )
        for a in raw_accounts
    ]
    return pick_extension_account(accounts, address=address, source=source)


async def open_extension_signer(
    *,
    address: str | None = None,
    source: str | None = None,
    host: str = "127.0.0.1",
    port: int = 39295,
) -> ExtensionSigner:
    """Open a bridge connection and return a ready-to-use signer."""
    client = BridgeClient(host=host, port=port)
    account = await select_extension_account(client, address=address, source=source)
    raw = await client.list_accounts()
    crypto = 0
    for a in raw:
        if a.get("address") == account.address:
            crypto = account_crypto_type(a)
            break
    return ExtensionSigner(client, account, crypto_type=crypto)
