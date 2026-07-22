"""The signing seam: anything that can sign an extrinsic.

tusdt-cli follows the same Signer protocol as btcli — the CLI never requires
a raw private key; it requires a :class:`Signer`: an address, a public key, a
crypto type, and a ``sign(payload)`` method.

The transport already awaits ``sign`` when it returns a coroutine, so signers
that round-trip to a device or a service (Ledger, extension bridge) fit the
same protocol.

Beyond the required protocol, signers may expose optional capabilities:
- ``sign_extrinsic_payload(payload_json) -> {"signature": "0x..."}``
  for extension-style signers that take Polkadot-JS SignerPayloadJSON.
- ``metadata_digest(SigningContext) -> bytes`` for signers that verify
  the runtime before signing (Ledger clear-signing).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

_ROLES = ("coldkey", "hotkey")


@runtime_checkable
class Signer(Protocol):
    """Anything that can sign an extrinsic payload.

    ``ss58_address`` is the chain account address. ``crypto_type`` selects
    the signature scheme: ``0`` = ed25519, ``1`` = sr25519.

    ``sign`` may be a plain function or a coroutine function — the transport
    awaits the result if needed, so hardware and remote signers can block on
    user approval without holding the event loop hostage.
    """

    @property
    def ss58_address(self) -> str: ...

    @property
    def public_key(self) -> bytes: ...

    @property
    def crypto_type(self) -> int: ...

    def sign(self, payload: bytes) -> bytes: ...


class WalletSigner:
    """A :class:`Signer` backed by a local keypair (software wallet).

    Public attributes come from the keypair; no unlock needed since the
    keypair is already loaded. Follows btcli's WalletSigner pattern.
    """

    def __init__(self, keypair, ss58_address: str):
        self._keypair = keypair
        self._ss58_address = ss58_address

    @property
    def ss58_address(self) -> str:
        return self._ss58_address

    @property
    def public_key(self) -> bytes:
        return bytes(self._keypair.public_key)

    @property
    def crypto_type(self) -> int:
        return getattr(self._keypair, "crypto_type", 0)

    def sign(self, payload: bytes) -> bytes:
        return self._keypair.sign(payload)

    def __repr__(self) -> str:
        return f"WalletSigner({self._ss58_address})"
