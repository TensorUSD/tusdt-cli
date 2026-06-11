"""Bittensor wallet filesystem interaction.

Reads wallet files directly from ~/.bittensor/wallets/ without depending
on the bittensor-wallet package.  Supports listing wallets (public-key only,
no password needed) and loading keypairs for signing (decrypts encrypted
coldkeys with NaCl/Argon2id).
"""

import json
import os
from dataclasses import dataclass, field
from getpass import getpass
from pathlib import Path

from substrateinterface import Keypair

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class HotkeyInfo:
    """Represents a single hotkey entry inside a wallet."""

    name: str
    ss58_address: str | None = None
    is_encrypted: bool = False


@dataclass
class WalletInfo:
    """Represents a bittensor wallet (coldkey + hotkeys)."""

    name: str
    path: str
    coldkey_address: str | None = None
    hotkeys: list[HotkeyInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def get_default_wallet_path() -> Path:
    """Return the default bittensor wallet directory."""
    return Path.home() / ".bittensor" / "wallets"


def _read_ss58_from_pubfile(path: Path) -> str | None:
    """Extract an SS58 address from a coldkeypub.txt or hotkey JSON file."""
    try:
        with open(path) as f:
            data = json.load(f)
        ss58 = data.get("ss58Address") or data.get("ss58_address")
        if ss58:
            return str(ss58)
        pub_hex = data.get("publicKey") or data.get("public_key")
        if pub_hex:
            if pub_hex.startswith("0x"):
                pub_hex = pub_hex[2:]
            kp = Keypair(public_key=bytes.fromhex(pub_hex), ss58_format=42)
            return kp.ss58_address
        return None
    except Exception:
        return None


def _is_encrypted(path: Path) -> bool:
    """Return True if *path* is an encrypted (non-JSON) keyfile."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        json.loads(raw)
        return False
    except (json.JSONDecodeError, UnicodeDecodeError):
        return True


_NACL_SALT = bytes.fromhex("137183dff15a09bc9c90b5518739e9b1")


def _decrypt_keyfile(path: Path, password: str) -> dict:
    """Decrypt a NaCl/Argon2i-encrypted bittensor keyfile.

    Bittensor coldkey format: ``$NACL`` (5 bytes) + nonce (24 bytes) + ciphertext.
    Key is derived via Argon2i with a well-known hardcoded salt.
    """
    from nacl import encoding, pwhash, secret

    with open(path, "rb") as f:
        raw = f.read()

    if not raw.startswith(b"$NACL"):
        raise ValueError(f"Not a NaCl-encrypted keyfile: {path}")

    nonce = raw[5:29]
    ciphertext = raw[29:]

    box = secret.SecretBox(
        pwhash.argon2i.kdf(
            secret.SecretBox.KEY_SIZE,
            password.encode("utf-8"),
            _NACL_SALT,
            opslimit=pwhash.argon2i.OPSLIMIT_SENSITIVE,
            memlimit=pwhash.argon2i.MEMLIMIT_SENSITIVE,
            encoder=encoding.RawEncoder,
        )
    )
    decrypted = box.decrypt(ciphertext, nonce)
    return json.loads(decrypted)


def _keypair_from_keydata(data: dict) -> Keypair:
    """Build a ``Keypair`` from the JSON data inside a bittensor keyfile."""
    if "secretPhrase" in data:
        return Keypair.create_from_mnemonic(data["secretPhrase"], ss58_format=42)
    if "secretSeed" in data:
        seed = data["secretSeed"]
        if isinstance(seed, str):
            if not seed.startswith("0x"):
                seed = "0x" + seed
        return Keypair.create_from_seed(seed, ss58_format=42)
    if "privateKey" in data:
        pk = data["privateKey"]
        if isinstance(pk, str):
            if pk.startswith("0x"):
                pk = pk[2:]
            pk_bytes = bytes.fromhex(pk)
        else:
            pk_bytes = bytes(pk)
        return Keypair(private_key=pk_bytes, ss58_format=42)
    raise ValueError("Keyfile does not contain a recognised private-key format")


def _load_keyfile(path: Path, password: str | None = None) -> Keypair:
    """Load a keyfile (encrypted or plain) and return a Keypair."""
    if _is_encrypted(path):
        if password is None:
            password = getpass(f"Enter password for {path.name}: ")
        data = _decrypt_keyfile(path, password)
    else:
        with open(path) as f:
            data = json.load(f)
    return _keypair_from_keydata(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_ss58(name_or_address: str, wallet_path: str | None = None) -> str:
    """Resolve a wallet name or SS58 address to an SS58 address.

    If *name_or_address* matches a wallet directory, the coldkey address
    is read from ``coldkeypub.txt`` (no password required).
    Otherwise the value is returned unchanged (assumed to be SS58).
    """
    wp = Path(wallet_path).expanduser() if wallet_path else get_default_wallet_path()
    wallet_dir = wp / name_or_address
    if wallet_dir.is_dir():
        ss58 = _read_ss58_from_pubfile(wallet_dir / "coldkeypub.txt")
        if ss58:
            return ss58
        raise ValueError(f"Wallet '{name_or_address}' found but coldkeypub.txt is missing or unreadable")
    return name_or_address


def list_wallets(wallet_path: str | None = None) -> list[WalletInfo]:
    """Scan the wallet directory and return wallet info without decrypting keys."""
    wp = Path(wallet_path).expanduser() if wallet_path else get_default_wallet_path()
    if not wp.exists():
        return []

    wallets: list[WalletInfo] = []
    for entry in sorted(wp.iterdir()):
        if not entry.is_dir():
            continue

        coldkey_address = _read_ss58_from_pubfile(entry / "coldkeypub.txt")

        hotkeys_dir = entry / "hotkeys"
        hotkey_list: list[HotkeyInfo] = []
        if hotkeys_dir.exists() and hotkeys_dir.is_dir():
            for hk in sorted(hotkeys_dir.iterdir()):
                if not hk.is_file():
                    continue
                if hk.name.endswith(".pub") or hk.name.endswith("pub.txt"):
                    continue
                encrypted = _is_encrypted(hk)
                hk_address: str | None = None
                if not encrypted:
                    hk_address = _read_ss58_from_pubfile(hk)
                hotkey_list.append(HotkeyInfo(name=hk.name, ss58_address=hk_address, is_encrypted=encrypted))

        wallets.append(
            WalletInfo(
                name=entry.name,
                path=str(wp),
                coldkey_address=coldkey_address,
                hotkeys=hotkey_list,
            )
        )
    return wallets


def load_coldkey(
    wallet_name: str,
    wallet_path: str | None = None,
    password: str | None = None,
) -> Keypair:
    """Load and (if necessary) decrypt the coldkey for *wallet_name*."""
    wp = Path(wallet_path).expanduser() if wallet_path else get_default_wallet_path()
    coldkey_file = wp / wallet_name / "coldkey"
    if not coldkey_file.exists():
        raise FileNotFoundError(f"Coldkey not found at {coldkey_file}")
    return _load_keyfile(coldkey_file, password)


def load_hotkey(
    wallet_name: str,
    hotkey_name: str = "default",
    wallet_path: str | None = None,
) -> Keypair:
    """Load an (unencrypted) hotkey file and return its Keypair."""
    wp = Path(wallet_path).expanduser() if wallet_path else get_default_wallet_path()
    hotkey_file = wp / wallet_name / "hotkeys" / hotkey_name
    if not hotkey_file.exists():
        raise FileNotFoundError(f"Hotkey not found at {hotkey_file}")
    if _is_encrypted(hotkey_file):
        raise ValueError(f"Hotkey '{hotkey_name}' is encrypted; encrypted hotkeys are not supported")
    with open(hotkey_file) as f:
        data = json.load(f)
    return _keypair_from_keydata(data)


def get_signer_keypair(config: dict) -> Keypair:
    """Resolve the signing keypair from the current configuration.

    Resolution order:
      1. ``signer`` field – treated as a file path if it exists on disk,
         otherwise as a mnemonic seed phrase.
      2. ``wallet_name`` field – loads the coldkey (prompts for password
         when encrypted).
    """
    signer = config.get("signer")
    if signer:
        expanded = os.path.expanduser(signer)
        if os.path.isfile(expanded):
            return _load_keyfile(Path(expanded))
        return Keypair.create_from_mnemonic(signer, ss58_format=42)

    wallet_name = config.get("wallet_name")
    if wallet_name:
        return load_coldkey(wallet_name, config.get("wallet_path"))

    raise ValueError(
        "No signer configured.  Either pass --wallet-name <name> on the command,\n"
        "or pre-configure with:\n"
        "  tusdt config set --signer '<seed phrase>'\n"
        "  tusdt config set --wallet-name <name>"
    )


def get_reader_keypair(config: dict) -> Keypair:
    """Return a keypair suitable for read-only contract queries.

    Always returns the ``//Alice`` dev URI keypair.  Read-only dry-runs
    don't require a real wallet – any valid keypair will do.
    """
    return Keypair.create_from_uri("//Alice", ss58_format=42)
