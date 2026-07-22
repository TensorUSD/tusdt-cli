"""Per-invocation CLI state — the single choke-point for config, signing,
connection lifecycle, and error handling.

Modeled on btcli's ``cli/context.py`` AppContext pattern.  The root Click
callback builds one ``CLIContext`` and stashes it on ``ctx.obj``.  Every
command retrieves it and runs all chain work through ``run_read`` (queries)
or ``submit`` (mutations), so error rendering, output formatting, and
connection management live in one place.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from substrateinterface import Keypair

from tusdt_cli.client import TUSDTClient
from tusdt_cli.config import load_config
from tusdt_cli.errors import REMEDIATION, ErrorCode, TUSDTError
from tusdt_cli.logs import setup_logging
from tusdt_cli.output import Output
from tusdt_cli.wallet import get_reader_keypair, get_signer_keypair

T = TypeVar("T")

logger = logging.getLogger("tusdt_cli")


@dataclass
class CLIContext:
    """Mutable per-invocation state shared across all commands.

    Populated by the root callback from global CLI flags, then each command
    can further refine fields (network, wallet_name, etc.) before calling
    :meth:`run_read` or :meth:`submit`.
    """

    network: str = "finney"
    wallet_name: str | None = None
    use_json: bool = False
    quiet: bool = False
    assume_yes: bool = False
    verbosity: int = 0
    dry_run: bool = False
    signer_backend: str | None = None
    ledger_account: int = 0
    ledger_index: int = 0
    # Extension signing options (matches btcli's pattern)
    signer_address: str | None = None
    extension_source: str | None = None
    extension_browser: str | None = None
    output: Output = field(default_factory=Output)
    _ledger_signer: Any | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        setup_logging(verbosity=self.verbosity, quiet=self.quiet)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def uses_ledger(self) -> bool:
        """Return True if the signer backend is set to 'ledger'."""
        return (self.signer_backend or "").strip().lower() == "ledger"

    def uses_extension(self) -> bool:
        """Return True if the signer backend is set to 'extension'."""
        return (self.signer_backend or "").strip().lower() == "extension"

    def uses_external_signer(self) -> bool:
        """Return True if signing via a device or extension (not local wallet)."""
        return self.uses_ledger() or self.uses_extension()

    def ledger_signer(self):
        """Return the singleton LedgerSigner for this invocation (lazy, cached)."""
        if self._ledger_signer is None:
            from tusdt_cli.ledger import LedgerSigner, find_ledger_device

            device = find_ledger_device()
            self._ledger_signer = LedgerSigner(device, account=self.ledger_account, index=self.ledger_index)
            if not self.output.quiet and not self.output.json_mode:
                self.output.info(
                    f"using ledger account {self._ledger_signer.ss58_address} "
                    f"({self._ledger_signer.derivation_path})"
                )
        return self._ledger_signer

    def extension_signer(self):
        """Return an ExtensionSigner connected via the browser extension bridge.

        Starts the bridge daemon if needed, opens the bridge page, and
        returns a ready-to-use signer. Async — blocks until connected.
        """
        import asyncio

        from tusdt_cli.extension import (
            ensure_bridge,
            open_extension_signer,
        )

        ensure_bridge(
            browser=self.extension_browser,
            fresh=False,
        )
        return asyncio.run(
            open_extension_signer(
                address=self.signer_address,
                source=self.extension_source,
            )
        )

    def make_config(self) -> dict[str, Any]:
        """Resolve the full config for this invocation.

        Loads from disk, applies network/wallet overrides from the
        invocation, and syncs output modes.
        """
        cfg = load_config(network=self.network)
        if self.wallet_name:
            cfg["wallet_name"] = self.wallet_name

        self.output.json_mode = self.use_json
        self.output.quiet = self.quiet
        self.output.network = cfg.get("network", self.network)

        return cfg

    # ------------------------------------------------------------------
    # Read (query)
    # ------------------------------------------------------------------

    def run_read(self, fn: Callable[[TUSDTClient], T]) -> T:
        """Open a client, call *fn*, handle errors uniformly.

        Usage from a read-only command::

            state.run_read(lambda client: client.balance_of(keypair, account))
        """
        config = self.make_config()
        try:
            client = TUSDTClient(config)
            return fn(client)
        except TUSDTError as exc:
            self.output.error(exc.message, help=REMEDIATION.get(exc.code))
            sys.exit(1)
        except Exception as exc:
            logger.exception("Unexpected error during read")
            err = TUSDTError(str(exc), code=ErrorCode.UNKNOWN)
            self.output.error(err.message, help=REMEDIATION.get(err.code))
            sys.exit(1)

    # ------------------------------------------------------------------
    # Submit (mutation)
    # ------------------------------------------------------------------

    def submit(self, fn: Callable[[TUSDTClient, Keypair], Any]) -> dict[str, Any] | None:
        """Resolve the signer, open a client, call *fn*, and render the result.

        Usage from a write command::

            state.submit(lambda client, kp: client.create_vault(kp, amount))

        When ``self.dry_run`` is True, the client is flagged for dry-run mode,
        the result is rendered via :meth:`Output.dry_run_result`, and ``None``
        is returned.
        """
        config = self.make_config()

        # --- resolve signer: extension > ledger > local wallet ---
        if self.uses_extension():
            ext_signer = self.extension_signer()
            from tusdt_cli.ledger import LedgerKeypair

            # Wrap extension signer as a Keypair adapter for substrate-interface.
            keypair = LedgerKeypair(ext_signer, ext_signer.ss58_address, ext_signer.public_key)
        elif self.uses_ledger():
            from tusdt_cli.ledger import LedgerKeypair

            signer = self.ledger_signer()
            keypair = LedgerKeypair(signer, signer.ss58_address, signer.get_public_key())
        else:
            try:
                keypair = get_signer_keypair(config)
            except Exception as exc:
                err = TUSDTError(str(exc), code=ErrorCode.WALLET_NOT_FOUND)
                self.output.error(err.message, help=REMEDIATION.get(err.code))
                sys.exit(1)

        self.output.info(f"Signer: {keypair.ss58_address}")

        try:
            client = TUSDTClient(config)
            if self.dry_run:
                client.dry_run = True
            result = fn(client, keypair)

            if self.dry_run:
                from tusdt_cli.client import DryRunResult

                if isinstance(result, DryRunResult):
                    self.output.dry_run_result(result)
                sys.exit(0)

            self.output.tx_result(result)
            return result
        except TUSDTError as exc:
            self.output.error(exc.message, help=REMEDIATION.get(exc.code))
            sys.exit(1)
        except Exception as exc:
            logger.exception("Unexpected error during submit")
            err = TUSDTError(str(exc), code=ErrorCode.UNKNOWN)
            self.output.error(err.message, help=REMEDIATION.get(err.code))
            sys.exit(1)

    # ------------------------------------------------------------------
    # Convenience: reader keypair (for read-only commands that need one)
    # ------------------------------------------------------------------

    def get_reader_keypair(self) -> Keypair:
        """Return the stateless reader keypair (always //Alice)."""
        return get_reader_keypair(self.make_config())
