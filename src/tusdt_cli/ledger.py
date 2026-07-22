"""Ledger hardware wallet support for the TUSDT CLI.

Provides :class:`LedgerSigner` (device communication via USB HID) that satisfies
the :class:`~tusdt_cli.signing.Signer` protocol, and :class:`LedgerKeypair`
(a :class:`substrateinterface.Keypair` subclass for backward compatibility).

Based on the Polkadot generic Ledger app (SLIP-44 coin type 354, derivation
path ``m/44'/354'/ACCOUNT'/0'/INDEX'``). Follows btcli's Ledger architecture.

Usage::

    from tusdt_cli.ledger import LedgerSigner, LedgerKeypair, find_ledger_device

    # Direct Signer protocol usage (preferred):
    signer = LedgerSigner(account=0, index=0)
    address = signer.ss58_address
    pubkey = signer.public_key
    sig = signer.sign(payload)

    # Backward-compatible Keypair adapter:
    device = find_ledger_device()
    signer = LedgerSigner(device, account=0, index=0)
    keypair = LedgerKeypair(signer, signer.ss58_address, signer.get_public_key())

The ``hid`` dependency is optional — install with ``pip install tusdt-cli[ledger]``.
"""

from __future__ import annotations

import struct
from typing import Any

from substrateinterface import Keypair, ScaleBytes

from tusdt_cli.errors import ErrorCode, TUSDTError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_VENDOR_ID = 0x2C97
LEDGER_USAGE_PAGE = 0xFFA0

# Polkadot generic app CLA + instruction codes
POLKADOT_CLA = 0x90
POLKADOT_INS_GET_VERSION = 0x00
POLKADOT_INS_GET_PUBKEY = 0x01
POLKADOT_INS_SIGN = 0x02

# BIP44 hardened flag
_HARDENED = 0x80000000

# SLIP-44 registered coin type for Polkadot
_COIN_TYPE_POLKADOT = 354

# SW (status word) codes
_SW_OK = 0x9000
_SW_USER_REFUSED = 0x6986

# Chain constants baked into the runtime's metadata hash
# (matches btcli: SS58Format=42, Decimals=9, TokenSymbol="TAO")
_SS58_FORMAT = 42
_DECIMALS = 9
_TOKEN_SYMBOL = "TAO"


class LedgerError(TUSDTError):
    """Raised when Ledger communication fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code=ErrorCode.LEDGER_ERROR)


# ---------------------------------------------------------------------------
# HID device discovery
# ---------------------------------------------------------------------------


def find_ledger_device() -> Any:
    """Discover and open the first connected Ledger device with the Polkadot app.

    Returns an ``hid.device`` instance on success.
    Raises :class:`LedgerError` if no device is found or if the ``hid``
    package is not installed.
    """
    try:
        import hid
    except ImportError:
        raise LedgerError(
            "The 'hid' package is required for Ledger support. Install it with: pip install tusdt-cli[ledger]"
        ) from None

    devices = hid.enumerate(LEDGER_VENDOR_ID, None)
    polkadot_devices = [d for d in devices if d.get("usage_page") == LEDGER_USAGE_PAGE]

    if not polkadot_devices:
        raise LedgerError(
            "No Ledger device found with the Polkadot app open. "
            "Check the device is connected, unlocked, and the Polkadot app is open."
        )

    dev = hid.Device()
    dev.open(polkadot_devices[0]["vendor_id"], polkadot_devices[0]["product_id"])  # ty: ignore
    return dev


# ---------------------------------------------------------------------------
# BIP44 derivation
# ---------------------------------------------------------------------------


def _derive_path_bytes(account: int, index: int) -> bytes:
    """Serialize a BIP44 derivation path for the Polkadot Ledger app.

    Path: ``m/44'/354'/ACCOUNT'/0'/INDEX'``

    Returns the path as length-prefixed, hardened u32 values (big-endian).
    """
    path = [
        44 | _HARDENED,
        _COIN_TYPE_POLKADOT | _HARDENED,
        account | _HARDENED,
        0,  # change (external chain)
        index | _HARDENED,
    ]
    buf = struct.pack("<I", len(path))
    for component in path:
        buf += struct.pack("<I", component)
    return buf


# ---------------------------------------------------------------------------
# APDU helpers
# ---------------------------------------------------------------------------


def _apdu_command(ins: int, data: bytes = b"", p1: int = 0x00, p2: int = 0x00) -> bytes:
    """Build an APDU command for the Polkadot Ledger app."""
    header = bytes([POLKADOT_CLA, ins, p1, p2, len(data)])
    return header + data


def _apdu_response(data: bytes) -> tuple[bytes, int]:
    """Split an APDU response into (payload, status_word)."""
    if len(data) < 2:
        raise LedgerError(f"Truncated APDU response ({len(data)} bytes)")
    return data[:-2], (data[-2] << 8) | data[-1]


def _hid_write(device: Any, apdu: bytes) -> None:
    """Write an APDU command wrapped in a 64-byte HID report."""
    report = b"\x00" + apdu
    device.write(report)


def _hid_read(device: Any, timeout_ms: int = 30000) -> bytes:
    """Read a complete APDU response from the HID device.

    Reads 64-byte HID reports until a complete response is received.
    The first byte of each report is a report ID (ignored).
    """
    chunk = device.read(64, timeout_ms=timeout_ms)
    if not chunk:
        raise LedgerError("Timeout reading from Ledger device")
    return bytes(chunk[1:])


# ---------------------------------------------------------------------------
# LedgerSigner
# ---------------------------------------------------------------------------


class LedgerSigner:
    """Signs payloads via a connected Ledger hardware device.

    Satisfies the :class:`~tusdt_cli.signing.Signer` protocol. Manages the
    HID connection lifecycle and wraps the APDU protocol for public-key
    retrieval, address confirmation, and signing. The Polkadot generic app
    must be open on the device.

    Follows btcli's Ledger architecture with:
    - ``crypto_type = 0`` (ed25519 — what the generic app signs with)
    - ``_SS58_FORMAT = 42``, ``_DECIMALS = 9``, ``_TOKEN_SYMBOL = "TAO"``

    Parameters:
        device: An open ``hid.device`` instance (from :func:`find_ledger_device`).
                If None, ``find_ledger_device()`` is called automatically.
        account: BIP44 account index (default 0).
        index: BIP44 address index (default 0).
    """

    crypto_type = 0  # ed25519 — what the generic app uses

    def __init__(self, device: Any = None, account: int = 0, index: int = 0) -> None:
        if device is None:
            device = find_ledger_device()
        self._device = device
        self.account = account
        self.index = index
        self._public_key: bytes | None = None
        self._ss58_address: str | None = None

    # -- derivation path ---------------------------------------------------

    @property
    def derivation_path(self) -> str:
        return f"m/44'/{_COIN_TYPE_POLKADOT}'/{self.account}'/0'/{self.index}'"

    # -- app version -------------------------------------------------------

    def app_version(self) -> tuple[int, int, int]:
        """The generic app's version — also an "is the app open?" probe."""
        apdu = _apdu_command(POLKADOT_INS_GET_VERSION)
        _hid_write(self._device, apdu)

        data, sw = _apdu_response(_hid_read(self._device))
        if sw != _SW_OK:
            raise LedgerError(f"Ledger APDU error (GET_VERSION): SW={sw:#06x}")

        if len(data) < 3:
            raise LedgerError(f"Truncated version response ({len(data)} bytes)")
        return data[0], data[1], data[2]

    # -- public key --------------------------------------------------------

    def get_public_key(self) -> bytes:
        """Retrieve the compressed public key from the device (cached).

        Returns the 32-byte ed25519 public key.
        """
        if self._public_key is not None:
            return self._public_key

        path_bytes = _derive_path_bytes(self.account, self.index)
        apdu = _apdu_command(POLKADOT_INS_GET_PUBKEY, path_bytes)
        _hid_write(self._device, apdu)

        data, sw = _apdu_response(_hid_read(self._device))
        if sw != _SW_OK:
            raise LedgerError(f"Ledger APDU error (GET_PUBKEY): SW={sw:#06x}")

        # Response: compressed public key (32 bytes) + SS58 address string
        self._public_key = data[:32]
        self._ss58_address = data[32:].decode("utf-8", errors="replace")
        return self._public_key

    @property
    def public_key(self) -> bytes:
        """Public key as bytes (Signer protocol)."""
        return self.get_public_key()

    @property
    def ss58_address(self) -> str:
        """The SS58 address derived from the device (lazy, cached)."""
        if self._ss58_address is None:
            self.get_public_key()
        assert self._ss58_address is not None
        return self._ss58_address

    @property
    def ss58_format(self) -> int:
        return _SS58_FORMAT

    def confirm_address(self) -> str:
        """Re-derive the address with on-device display and return it after
        the user approves. Use to verify the address on the trusted screen.

        Follows btcli's pattern: calls GET_PUBKEY with p2=0x01 (confirm).
        """
        path_bytes = _derive_path_bytes(self.account, self.index)
        apdu = _apdu_command(POLKADOT_INS_GET_PUBKEY, path_bytes, p2=0x01)
        _hid_write(self._device, apdu)

        data, sw = _apdu_response(_hid_read(self._device))
        if sw == _SW_USER_REFUSED:
            raise LedgerError("User refused address confirmation on the Ledger device")
        if sw != _SW_OK:
            raise LedgerError(f"Ledger APDU error (CONFIRM_ADDRESS): SW={sw:#06x}")

        address = data[32:].decode("utf-8", errors="replace")
        return address

    # -- signing -----------------------------------------------------------

    def sign(self, data: bytes) -> bytes:
        """Sign *data* with the Ledger device.

        The device will display the transaction for user approval.
        Returns the 64-byte signature.

        Note: This performs blind-signing via the Polkadot generic app.
        When the transport layer supports metadata proofs, prefer
        ``sign_unsigned_extrinsic`` for clear-signing with on-screen
        transaction details (matching btcli's security model).
        """
        path_bytes = _derive_path_bytes(self.account, self.index)
        payload = path_bytes + data

        apdu = _apdu_command(POLKADOT_INS_SIGN, payload)
        _hid_write(self._device, apdu)

        sig_data, sw = _apdu_response(_hid_read(self._device))

        if sw == _SW_USER_REFUSED:
            raise LedgerError("User refused the signing request on the Ledger device")
        if sw != _SW_OK:
            raise LedgerError(f"Ledger APDU error (SIGN): SW={sw:#06x}")

        return sig_data

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the HID connection to the device."""
        import contextlib

        with contextlib.suppress(Exception):
            self._device.close()

    def __repr__(self) -> str:
        return f"LedgerSigner({self.ss58_address}, path=m/44'/354'/{self.account}'/0'/{self.index}')"


# ---------------------------------------------------------------------------
# LedgerKeypair — substrateinterface.Keypair subclass
# ---------------------------------------------------------------------------


class LedgerKeypair(Keypair):
    """A :class:`Keypair` that delegates signing to a Ledger hardware wallet.

    Uses a dummy ``private_key`` placeholder (never exposed or used) because
    substrate-interface's ``Keypair.__init__`` requires one.  All signing is
    routed through :meth:`LedgerSigner.sign`.
    """

    def __init__(self, signer: LedgerSigner, ss58_address: str, public_key: bytes) -> None:
        self._signer = signer
        # Zeroed dummy private key — never used, sign() is overridden
        super().__init__(
            private_key=b"\x00" * 64,
            public_key=public_key,
            ss58_format=42,
            crypto_type=0,  # ed25519 — what the Polkadot generic app uses
        )
        self.ss58_address = ss58_address

    def sign(self, data: ScaleBytes | bytes | str, sr_format: bool = True) -> bytes:
        """Sign *data* via the connected Ledger device."""
        if isinstance(data, str):
            data = bytes.fromhex(data.replace("0x", ""))
        if isinstance(data, ScaleBytes):
            data = bytes(data.data)
        return self._signer.sign(data)
