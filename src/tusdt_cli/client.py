"""Substrate/ink! contract client for the TUSDT system.

Wraps ``SubstrateInterface`` and ``ContractInstance`` to provide typed
methods for the Vault, Token (ERC-20), Auction, Oracle, Governance, and
Treasury contracts.
"""

import logging
from dataclasses import dataclass, field
from time import sleep
from typing import Any, cast

from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.contracts import ContractInstance, ContractMetadata
from substrateinterface.exceptions import ContractReadFailedException

from tusdt_cli.errors import ErrorCode, TUSDTError
from tusdt_cli.utils import (
    ContractError,
    console,
    unwrap_option,
    unwrap_plain,
    unwrap_result,
)

logger = logging.getLogger("tusdt_cli")

_PATCH_APPLIED = False


def _apply_metadata_patch() -> None:
    """Apply the monkey-patch to ContractMetadata for newer ink! metadata formats.

    The patch is applied at most once (idempotent). Called from
    TUSDTClient.__init__ so it is explicit rather than a side effect of
    importing this module.
    """
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return
    _PATCH_APPLIED = True

    _parse_metadata_original = ContractMetadata._ContractMetadata__parse_metadata  # ty: ignore

    def _patched_parse_metadata(self: ContractMetadata) -> None:
        self._ContractMetadata__convert_to_latest_metadata()

        # -- original checks (lines 140-154) --
        if "types" not in self.metadata_dict:
            raise ValueError("No 'types' directive present in metadata file")
        if "spec" not in self.metadata_dict:
            raise ValueError("'spec' directive not present in metadata file")
        if "constructors" not in self.metadata_dict["spec"]:
            raise ValueError("No constructors present in metadata file")
        if "messages" not in self.metadata_dict["spec"]:
            raise ValueError("No messages present in metadata file")
        if "source" not in self.metadata_dict:
            raise ValueError("'source' directive not present in metadata file")

        if "V0" in self.metadata_dict and tuple(
            int(x) for x in self.metadata_dict["metadataVersion"].split(".")
        ) < (0, 7, 0):
            self._ContractMetadata__type_offset = 1  # ty: ignore

        self.type_string_prefix = f"ink::{self.metadata_dict['source']['hash']}"

        if self.metadata_version == 0:
            for idx, _ in enumerate(self.metadata_dict["types"]):
                idx += self._ContractMetadata__type_offset
                if idx not in self.type_registry:
                    self.type_registry[idx] = self.get_type_string_for_metadata_type(idx)
        else:
            self.substrate.init_runtime()
            pr = self.substrate.runtime_config.create_scale_object("PortableRegistry")
            pr.encode({"types": self.metadata_dict["types"]})
            raw_types = pr["types"]
            if hasattr(raw_types, "value_object"):
                raw_types = raw_types.value_object
            self.substrate.runtime_config.update_from_scale_info_types(
                raw_types, prefix=self.type_string_prefix
            )

    ContractMetadata._ContractMetadata__parse_metadata = _patched_parse_metadata  # ty: ignore


def _decode_dispatch_error(err: Any) -> str:
    """Best-effort human-readable description of a DispatchError dict."""
    if isinstance(err, dict):
        if "Module" in err:
            mod = err["Module"]
            idx = mod.get("index", "?")
            raw = mod.get("error", "?")
            return f"Module error (pallet index {idx}, error {raw})"
        keys = list(err.keys())
        if keys:
            return str(err)
    return str(err)


_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds


def _connect_with_retry(rpc: str) -> SubstrateInterface:
    """Create a SubstrateInterface with retry on connection failure."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            logger.debug("Connecting to %s (attempt %d/%d)", rpc, attempt + 1, _MAX_RETRIES)
            return SubstrateInterface(
                url=rpc,
                use_remote_preset=True,
                type_registry={"types": {"Balance": "u64"}},
                ws_options={"max_size": 2**20, "close_timeout": 5},
            )
        except (ConnectionError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (attempt + 1)
                logger.warning(
                    "Connection to %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    rpc,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                    exc,
                )
                sleep(delay)

    raise TUSDTError(
        f"Cannot connect to {rpc} after {_MAX_RETRIES} attempts: {last_error}",
        code=ErrorCode.CONNECTION_FAILED,
    )


@dataclass
class DryRunResult:
    """Structured result of a contract dry-run execution."""

    method: str
    signer: str
    value: int = 0
    gas_required: dict[str, int] | None = None
    gas_consumed: dict[str, int] | None = None
    gas_ratio: float | None = None
    partial_fee: int | None = None
    is_success: bool = False
    return_value: Any | None = None
    debug_info: dict[str, Any] = field(default_factory=dict)


def _gas_to_int(gas: Any) -> int | None:
    """Extract a comparable gas value from a WeightV2 dict or scalar."""
    if gas is None:
        return None
    if isinstance(gas, dict):
        return int(gas.get("ref_time", 0))
    return int(gas)


class TUSDTClient:
    """High-level client for the TUSDT contract system (seven contracts).

    Accepts an optional ``_substrate`` kwarg for test injection.
    When ``None`` (the default), a real ``SubstrateInterface`` is created
    lazily on first access.
    """

    def __init__(self, config: dict[str, Any], _substrate: SubstrateInterface | None = None) -> None:
        _apply_metadata_patch()
        self.config = config
        self._substrate: SubstrateInterface | None = _substrate
        self.dry_run: bool = False
        self._vault: ContractInstance | None = None
        self._token: ContractInstance | None = None
        self._auction: ContractInstance | None = None
        self._oracle: ContractInstance | None = None
        self._governance: ContractInstance | None = None
        self._treasury: ContractInstance | None = None
        self._election: ContractInstance | None = None
        self._lending: ContractInstance | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def substrate(self) -> SubstrateInterface:
        if self._substrate is None:
            rpc = self.config.get("rpc")
            if not rpc:
                raise ValueError("RPC endpoint not configured. Run: tusdt config set --rpc <url>")
            self._substrate = _connect_with_retry(rpc)
        return self._substrate

    def _load_contract(self, address: str, metadata_path: str) -> ContractInstance:
        metadata = ContractMetadata.create_from_file(
            metadata_file=metadata_path,
            substrate=self.substrate,
        )
        return ContractInstance(
            contract_address=address,
            metadata=metadata,
            substrate=self.substrate,
        )

    # ------------------------------------------------------------------
    # Lazy contract accessors
    # ------------------------------------------------------------------

    @property
    def vault(self) -> ContractInstance:
        if self._vault is None:
            addr = self.config.get("vault_address")
            meta = self.config.get("vault_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Vault contract not configured. Run:\n"
                    "  tusdt config set --vault <address> --vault-metadata <path>"
                )
            self._vault = self._load_contract(addr, meta)
        return self._vault

    @property
    def token(self) -> ContractInstance:
        if self._token is None:
            addr = self.config.get("token_address")
            meta = self.config.get("token_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Token contract not configured. Run:\n"
                    "  tusdt config set --token <address> --token-metadata <path>"
                )
            self._token = self._load_contract(addr, meta)
        return self._token

    @property
    def auction(self) -> ContractInstance:
        if self._auction is None:
            addr = self.config.get("auction_address")
            meta = self.config.get("auction_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Auction contract not configured. Run:\n"
                    "  tusdt config set --auction <address> --auction-metadata <path>"
                )
            self._auction = self._load_contract(addr, meta)
        return self._auction

    @property
    def oracle(self) -> ContractInstance:
        if self._oracle is None:
            addr = self.config.get("oracle_address")
            meta = self.config.get("oracle_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Oracle contract not configured. Run:\n"
                    "  tusdt config set --oracle <address> --oracle-metadata <path>"
                )
            self._oracle = self._load_contract(addr, meta)
        return self._oracle

    @property
    def governance(self) -> ContractInstance:
        if self._governance is None:
            addr = self.config.get("governance_address")
            meta = self.config.get("governance_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Governance contract not configured. Run:\n"
                    "  tusdt config set --governance <address> --governance-metadata <path>"
                )
            self._governance = self._load_contract(addr, meta)
        return self._governance

    @property
    def treasury(self) -> ContractInstance:
        if self._treasury is None:
            addr = self.config.get("treasury_address")
            meta = self.config.get("treasury_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Treasury contract not configured. Run:\n"
                    "  tusdt config set --treasury <address> --treasury-metadata <path>"
                )
            self._treasury = self._load_contract(addr, meta)
        return self._treasury

    @property
    def election(self) -> ContractInstance:
        if self._election is None:
            addr = self.config.get("election_address")
            meta = self.config.get("election_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Election contract not configured. Run:\n"
                    "  tusdt config set --election <address> --election-metadata <path>"
                )
            self._election = self._load_contract(addr, meta)
        return self._election

    @property
    def lending(self) -> ContractInstance:
        if self._lending is None:
            addr = self.config.get("lending_address")
            meta = self.config.get("lending_metadata")
            if not addr or not meta:
                raise ValueError(
                    "Lending pool contract not configured. Run:\n"
                    "  tusdt config set --lending <address> --lending-metadata <path>"
                )
            self._lending = self._load_contract(addr, meta)
        return self._lending

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _read(
        self,
        contract: ContractInstance,
        keypair: Keypair,
        method: str,
        args: dict[str, Any] | None = None,
        value: int = 0,
        _silent: bool = False,
    ) -> Any:
        """Perform a dry-run read call, converting chain errors to ``ContractError``.

        When *_silent* is True the spinner is suppressed (used internally by
        ``_exec`` which manages its own progress display).
        """
        kwargs: dict[str, Any] = {
            "keypair": keypair,
            "method": method,
            "args": args or {},
        }
        if value:
            kwargs["value"] = value

        if _silent:
            try:
                return contract.read(**kwargs)
            except ContractReadFailedException as exc:
                msg = _decode_dispatch_error(exc.args[0] if exc.args else str(exc))
                raise ContractError(f"Contract query '{method}' failed: {msg}") from None

        with console.status(f"[bold cyan]Querying {method}..."):
            try:
                return contract.read(**kwargs)
            except ContractReadFailedException as exc:
                msg = _decode_dispatch_error(exc.args[0] if exc.args else str(exc))
                raise ContractError(f"Contract query '{method}' failed: {msg}") from None

    def _exec(
        self,
        contract: ContractInstance,
        keypair: Keypair,
        method: str,
        args: dict[str, Any] | None = None,
        value: int = 0,
    ) -> dict[str, Any] | DryRunResult:
        """Dry-run for gas estimation, then submit the extrinsic.

        When ``self.dry_run`` is True, the gas estimation is performed but the
        extrinsic is never submitted.  Returns a :class:`DryRunResult` instead
        of the normal extrinsic-hash dict.

        Shows a step-by-step progress spinner:
          1. Estimating gas...
          2. Submitting transaction...
          3. Finalized

        Returns a dict with ``extrinsic_hash`` and ``block_hash`` on success.
        Raises ``ContractError`` on failure.
        """
        if self.dry_run:
            return self._dry_run(contract, keypair, method, args, value)

        with console.status("[bold cyan]Estimating gas...") as status:
            gas_predict = self._read(contract, keypair, method, args, value, _silent=True)

            call_args = args or {}
            exec_kwargs: dict[str, Any] = {
                "keypair": keypair,
                "method": method,
                "args": call_args,
                "gas_limit": gas_predict.gas_required,
            }
            if value:
                exec_kwargs["value"] = value

            status.update("[bold cyan]Submitting transaction...")
            receipt = contract.exec(**exec_kwargs)

        if not receipt.is_success:
            raise ContractError(f"{method} failed: {receipt.error_message}")

        console.print("[bold green]Finalized[/bold green]")

        return {
            "extrinsic_hash": receipt.extrinsic_hash,
            "block_hash": receipt.block_hash,
        }

    def _dry_run(
        self,
        contract: ContractInstance,
        keypair: Keypair,
        method: str,
        args: dict[str, Any] | None = None,
        value: int = 0,
    ) -> DryRunResult:
        """Preview a contract call without submitting.

        Performs a read-only runtime simulation (same as gas estimation),
        decodes the return value, and attempts a fee estimate via the
        ``TransactionPaymentApi``.  No state change occurs.
        """
        logger.debug("Dry-run %s(args=%s, value=%s)", method, args, value)
        is_success = False
        return_value: Any | None = None
        debug_info: dict[str, Any] = {}

        try:
            gas_result = self._read(contract, keypair, method, args, value, _silent=True)
            gas_required = getattr(gas_result, "gas_required", None)
            gas_consumed = getattr(gas_result, "gas_consumed", None)
            debug_info["flags"] = getattr(gas_result, "flags", None)
            debug_info["did_revert"] = getattr(gas_result, "did_revert", False)

            # Decode contract return value
            try:
                contract_result = gas_result.contract_result_data
                if contract_result is not None:
                    value_obj = contract_result.value_object
                    if value_obj is not None and isinstance(value_obj, tuple) and len(value_obj) >= 2:
                        is_success = value_obj[0] == "Ok"
                        if is_success and value_obj[1] is not None:
                            return_value = (
                                value_obj[1].value if hasattr(value_obj[1], "value") else value_obj[1]
                            )
                        elif not is_success:
                            return_value = str(value_obj[1])
            except Exception:
                pass
        except ContractError as exc:
            return DryRunResult(
                method=method,
                signer=keypair.ss58_address,
                value=value,
                is_success=False,
                return_value=str(exc),
                debug_info=debug_info,
            )

        gas_req = _gas_to_int(gas_required)
        gas_con = _gas_to_int(gas_consumed)
        gas_ratio = (gas_con / gas_req) if gas_req and gas_con else None

        return DryRunResult(
            method=method,
            signer=keypair.ss58_address,
            value=value,
            gas_required=gas_required,
            gas_consumed=gas_consumed,
            gas_ratio=gas_ratio,
            partial_fee=self._estimate_fee(contract, keypair, method, args, value),
            is_success=is_success,
            return_value=return_value,
            debug_info=debug_info,
        )

    def _estimate_fee(
        self,
        contract: ContractInstance,
        keypair: Keypair,
        method: str,
        args: dict[str, Any] | None = None,
        value: int = 0,
    ) -> int | None:
        """Estimate the transaction fee via ``TransactionPaymentApi_query_info``.

        This is a read-only state call — no state change, no real signature
        needed.  Returns the ``partial_fee`` in native Planck units, or
        ``None`` if estimation fails.
        """
        try:
            sub = cast(Any, self.substrate)
            call = sub.generate_contract_call(
                contract_address=contract.contract_address,
                metadata=contract.metadata,
                method=method,
                args=args or {},
                value=value,
            )
            extrinsic = sub.create_signed_extrinsic(
                call=call,
                keypair=keypair,
                era={"period": 64},
                nonce=0,
                tip=0,
            )
            encoded = extrinsic.encode()
            encoded_hex = bytes(encoded.data).hex()
            result = sub.state_call(
                "TransactionPaymentApi_query_info",
                {"extrinsic": "0x" + encoded_hex, "len": len(encoded_hex) // 2},
            )
            if hasattr(result, "value"):
                return result.value.get("partial_fee")
            return result.get("partial_fee") if isinstance(result, dict) else None
        except Exception:
            return None

    # ==================================================================
    # VAULT OPERATIONS
    # ==================================================================

    def create_alpha_vault(
        self, keypair: Keypair, amount: int, netuid: int, value: int = 0
    ) -> dict[str, Any] | DryRunResult:
        """Create a new vault, pulling *amount* alpha stake on *netuid* as collateral.

        Uses the caller-forwarded ``caller_transfer_stake`` chain extension
        (function 25) to atomically pull the caller's alpha into the contract's
        coldkey. The *value* parameter pays the vault creation fee in native TAO.
        """
        return self._exec(
            self.vault,
            keypair,
            "create_alpha_vault",
            args={"amount": amount, "netuid": netuid},
            value=value,
        )

    def add_alpha_collateral(
        self, keypair: Keypair, vault_id: int, amount: int
    ) -> dict[str, Any] | DryRunResult:
        """Add alpha collateral to an existing vault via atomic pull."""
        return self._exec(
            self.vault,
            keypair,
            "add_alpha_collateral",
            args={"vault_id": vault_id, "amount": amount},
        )

    def borrow(self, keypair: Keypair, vault_id: int, amount: int) -> dict[str, Any] | DryRunResult:
        """Borrow TUSDT tokens against a vault's collateral."""
        return self._exec(self.vault, keypair, "borrow_token", args={"vault_id": vault_id, "amount": amount})

    def repay(self, keypair: Keypair, vault_id: int, amount: int) -> dict[str, Any] | DryRunResult:
        """Repay borrowed TUSDT tokens."""
        return self._exec(self.vault, keypair, "repay_token", args={"vault_id": vault_id, "amount": amount})

    def release_alpha_collateral(
        self, keypair: Keypair, vault_id: int, amount: int, dest_coldkey: str
    ) -> dict[str, Any] | DryRunResult:
        """Release alpha collateral from a vault to *dest_coldkey*."""
        return self._exec(
            self.vault,
            keypair,
            "release_alpha_collateral",
            args={"vault_id": vault_id, "amount": amount, "dest_coldkey": dest_coldkey},
        )

    def get_vault(self, keypair: Keypair, owner: str, vault_id: int) -> dict | None:
        """Query a single vault.  Returns ``None`` when not found."""
        result = self._read(self.vault, keypair, "get_vault", args={"owner": owner, "vault_id": vault_id})
        raw = unwrap_option(result)
        if raw is None:
            return None
        if isinstance(raw, dict):
            return raw
        try:
            return raw.value
        except AttributeError:
            return raw

    def list_vaults(self, keypair: Keypair, owner: str, page: int = 0) -> list[dict]:
        """Return a page of vaults for *owner* (PAGE_SIZE=10 per page)."""
        result = self._read(self.vault, keypair, "get_vaults", args={"owner": owner, "page": page})
        vaults = unwrap_result(result)
        if isinstance(vaults, list):
            return vaults
        return []

    def get_vaults_count(self, keypair: Keypair, owner: str) -> int:
        """Return the total number of vaults owned by *owner*."""
        result = self._read(self.vault, keypair, "get_vaults_count", args={"owner": owner})
        return unwrap_plain(result)

    def get_max_borrow(self, keypair: Keypair, owner: str, vault_id: int) -> int:
        """Return the maximum additional borrowable amount for a vault."""
        result = self._read(
            self.vault, keypair, "get_max_borrow", args={"owner": owner, "vault_id": vault_id}
        )
        return unwrap_result(result)

    def get_collateral_value(self, keypair: Keypair, owner: str, vault_id: int) -> int:
        """Return the collateral value (in borrowed-token terms) for a vault."""
        result = self._read(
            self.vault, keypair, "get_vault_collateral_value", args={"owner": owner, "vault_id": vault_id}
        )
        return unwrap_result(result)

    def get_total_debt(self, keypair: Keypair, owner: str) -> int:
        """Return the total debt for *owner* across all their vaults."""
        result = self._read(self.vault, keypair, "get_total_debt", args={"owner": owner})
        return unwrap_plain(result)

    def get_liquidation_auction_id(self, keypair: Keypair, owner: str, vault_id: int) -> int | None:
        """Return the active liquidation auction ID for a vault, or ``None``."""
        result = self._read(
            self.vault, keypair, "get_liquidation_auction_id", args={"owner": owner, "vault_id": vault_id}
        )
        return unwrap_option(result)

    def get_all_vaults(self, keypair: Keypair, page: int = 0) -> list[dict]:
        """Return a page of all vaults (any owner)."""
        result = self._read(self.vault, keypair, "get_all_vaults", args={"page": page})
        vaults = unwrap_result(result)
        if isinstance(vaults, list):
            return vaults
        return []

    def get_total_collateral_balance(self, keypair: Keypair) -> int:
        """Return the total collateral balance across all vaults."""
        result = self._read(self.vault, keypair, "get_total_collateral_balance")
        return unwrap_plain(result)

    def get_total_vaults_count(self, keypair: Keypair) -> int:
        """Return the total number of vaults across all owners."""
        result = self._read(self.vault, keypair, "get_total_vaults_count")
        return unwrap_plain(result)

    def get_contract_params(self, keypair: Keypair, netuid: int) -> dict:
        """Return the per-netuid vault contract parameters for *netuid*."""
        result = self._read(self.vault, keypair, "get_contract_params", args={"netuid": netuid})
        raw = unwrap_plain(result)
        return raw if isinstance(raw, dict) else raw

    def trigger_liquidation(
        self, keypair: Keypair, owner: str, vault_id: int
    ) -> dict[str, Any] | DryRunResult:
        """Trigger a liquidation auction for an undercollateralized vault."""
        return self._exec(
            self.vault, keypair, "trigger_liquidation_auction", args={"owner": owner, "vault_id": vault_id}
        )

    def settle_liquidation(
        self, keypair: Keypair, owner: str, vault_id: int
    ) -> dict[str, Any] | DryRunResult:
        """Settle a completed liquidation auction for a vault."""
        return self._exec(
            self.vault, keypair, "settle_liquidation_auction", args={"owner": owner, "vault_id": vault_id}
        )

    def get_token_address(self, keypair: Keypair) -> str:
        """Query the token contract address from the vault contract."""
        result = self._read(self.vault, keypair, "get_token_address")
        return unwrap_plain(result)

    def get_auction_address(self, keypair: Keypair) -> str:
        """Query the auction contract address from the vault contract."""
        result = self._read(self.vault, keypair, "get_auction_address")
        return unwrap_plain(result)

    def get_oracle_address(self, keypair: Keypair) -> str:
        """Query the oracle contract address from the vault contract."""
        result = self._read(self.vault, keypair, "get_oracle_address")
        return unwrap_plain(result)

    def get_vault_collateral_balance(self, keypair: Keypair, owner: str, vault_id: int) -> int | None:
        """Return the raw collateral balance for a specific vault, or None if not found."""
        result = self._read(
            self.vault,
            keypair,
            "get_vault_collateral_balance",
            args={"owner": owner, "vault_id": vault_id},
        )
        return unwrap_option(result)

    # ==================================================================
    # VAULT GOVERNANCE OPERATIONS
    # ==================================================================

    def get_governance(self, keypair: Keypair) -> str:
        """Return the current governance account address."""
        result = self._read(self.vault, keypair, "governance")
        return unwrap_plain(result)

    def get_vault_hotkey(self, keypair: Keypair) -> str:
        """Return the vault's staking hotkey address."""
        result = self._read(self.vault, keypair, "get_vault_hotkey")
        return unwrap_plain(result)

    def get_active_liquidation_count(self, keypair: Keypair) -> int:
        """Return the number of vaults currently in active liquidation auctions."""
        result = self._read(self.vault, keypair, "get_active_liquidation_count")
        return unwrap_plain(result)

    def get_platform(self, keypair: Keypair) -> str:
        """Return the current platform account address."""
        result = self._read(self.vault, keypair, "platform")
        return unwrap_plain(result)

    def is_paused(self, keypair: Keypair) -> bool:
        """Return whether the vault contract is paused."""
        result = self._read(self.vault, keypair, "paused")
        return unwrap_plain(result)

    def get_pending_contract_params_update(self, keypair: Keypair, netuid: int) -> dict | None:
        """Return the pending per-netuid contract parameter update, if any."""
        result = self._read(
            self.vault, keypair, "get_pending_contract_params_update", args={"netuid": netuid}
        )
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def update_governance(self, keypair: Keypair, new_governance: str) -> dict[str, Any] | DryRunResult:
        """Transfer governance to a new account."""
        return self._exec(self.vault, keypair, "update_governance", args={"new_governance": new_governance})

    def update_platform(self, keypair: Keypair, new_platform: str) -> dict[str, Any] | DryRunResult:
        """Update the platform account."""
        return self._exec(self.vault, keypair, "update_platform", args={"new_platform": new_platform})

    def pause_contract(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Pause the vault contract."""
        return self._exec(self.vault, keypair, "pause")

    def unpause_contract(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Unpause the vault contract."""
        return self._exec(self.vault, keypair, "unpause")

    def set_contract_params(
        self,
        keypair: Keypair,
        netuid: int,
        params: dict[str, Any],
    ) -> dict[str, Any] | DryRunResult:
        """Schedule a per-netuid contract parameter update with timelock.

        Reads current on-chain params for *netuid*, merges with user-supplied
        changes, and sends the complete VaultContractParamsConfig struct.
        """
        current = unwrap_plain(
            self._read(self.vault, keypair, "get_contract_params", args={"netuid": netuid})
        )
        if not isinstance(current, dict):
            raise ContractError(f"Expected dict from get_contract_params, got {type(current).__name__}")
        merged = dict(current)
        merged.update(params)
        return self._exec(
            self.vault,
            keypair,
            "set_contract_params",
            args={"netuid": netuid, "params": merged},
        )

    def execute_contract_params_update(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Execute the pending per-netuid contract parameter update after timelock."""
        return self._exec(self.vault, keypair, "execute_contract_params_update", args={"netuid": netuid})

    def cancel_contract_params_update(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Cancel the pending per-netuid contract parameter update."""
        return self._exec(self.vault, keypair, "cancel_contract_params_update", args={"netuid": netuid})

    def set_approved_netuid(
        self, keypair: Keypair, netuid: int, approved: bool
    ) -> dict[str, Any] | DryRunResult:
        """Approve or revoke a subnet for vault collateral (governance only)."""
        return self._exec(
            self.vault,
            keypair,
            "set_approved_netuid",
            args={"netuid": netuid, "approved": approved},
        )

    def is_approved_netuid(self, keypair: Keypair, netuid: int) -> bool:
        """Return whether *netuid* is approved for vault collateral."""
        result = self._read(self.vault, keypair, "is_approved_netuid", args={"netuid": netuid})
        return unwrap_plain(result)

    def claim_excess_alpha(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Claim excess alpha staking rewards on *netuid* (governance only).

        Excess = actual contract stake minus total collateral.  The excess is
        unstaked to native TAO and transferred to the treasury.
        """
        return self._exec(self.vault, keypair, "claim_excess_alpha", args={"netuid": netuid})

    def set_vault_hotkey(
        self, keypair: Keypair, new_hotkey: str, netuids: list[int]
    ) -> dict[str, Any] | DryRunResult:
        """Migrate the vault's staking hotkey to a new address (governance only).

        Moves all alpha stake on the specified netuids from the current hotkey
        to *new_hotkey* using chain-extension ``move_stake``. Reverts if any
        liquidation auction is active.
        """
        return self._exec(
            self.vault,
            keypair,
            "set_vault_hotkey",
            args={"new_hotkey": new_hotkey, "netuids": netuids},
        )

    def transfer_native_to_treasury(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Transfer the vault's entire native TAO balance to the treasury (governance only).

        Reverts if any liquidation auction is active.
        """
        return self._exec(self.vault, keypair, "transfer_native_to_treasury", args={})

    def set_global_params(self, keypair: Keypair, config: dict[str, Any]) -> dict[str, Any] | DryRunResult:
        """Schedule a global params update with timelock (governance only)."""
        return self._exec(self.vault, keypair, "set_global_params", args={"config": config})

    def execute_global_params_update(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Execute the pending global params update after timelock (permissionless)."""
        return self._exec(self.vault, keypair, "execute_global_params_update")

    def cancel_global_params_update(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Cancel the pending global params update (governance only)."""
        return self._exec(self.vault, keypair, "cancel_global_params_update")

    def get_global_params(self, keypair: Keypair) -> dict:
        """Return the vault global parameters."""
        result = self._read(self.vault, keypair, "get_global_params")
        raw = unwrap_plain(result)
        return raw if isinstance(raw, dict) else raw

    def claim_surplus_tusdt(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Claim surplus TUSDT tokens held by the vault contract."""
        return self._exec(self.vault, keypair, "claim_surplus_tusdt", args={"amount": amount})

    def vault_get_treasury(self, keypair: Keypair) -> str:
        """Return the treasury address from the vault contract."""
        result = self._read(self.vault, keypair, "treasury")
        return unwrap_plain(result)

    def vault_update_treasury(self, keypair: Keypair, new_treasury: str) -> dict[str, Any] | DryRunResult:
        """Update the treasury address in the vault contract (governance only)."""
        return self._exec(self.vault, keypair, "update_treasury", args={"new_treasury": new_treasury})

    def vault_emergency_drain(self, keypair: Keypair, recipient: str) -> dict[str, Any] | DryRunResult:
        """Emergency drain native balance from the vault (TESTNET ONLY, governance)."""
        return self._exec(self.vault, keypair, "emergency_drain", args={"recipient": recipient})

    # ---- Vault: upgrade / migration ----

    def vault_set_token_controller(
        self, keypair: Keypair, new_controller: str
    ) -> dict[str, Any] | DryRunResult:
        """Transfer the ERC20 token controller to a new account (vault governance only)."""
        return self._exec(
            self.vault, keypair, "set_token_controller", args={"new_controller": new_controller}
        )

    def vault_update_auction_address(
        self, keypair: Keypair, new_auction: str
    ) -> dict[str, Any] | DryRunResult:
        """Update the stored auction contract address (vault governance only)."""
        return self._exec(self.vault, keypair, "update_auction_address", args={"new_auction": new_auction})

    def vault_update_oracle_address(self, keypair: Keypair, new_oracle: str) -> dict[str, Any] | DryRunResult:
        """Update the stored oracle contract address (vault governance only)."""
        return self._exec(self.vault, keypair, "update_oracle_address", args={"new_oracle": new_oracle})

    def vault_update_token_address(self, keypair: Keypair, new_token: str) -> dict[str, Any] | DryRunResult:
        """Update the stored token contract address (vault governance only)."""
        return self._exec(self.vault, keypair, "update_token_address", args={"new_token": new_token})

    # ==================================================================
    # GOVERNANCE OPERATIONS
    # ==================================================================

    # --- Read queries ---

    def get_maintainer(self, keypair: Keypair) -> str:
        """Return the current maintainer account address."""
        result = self._read(self.governance, keypair, "maintainer")
        return unwrap_plain(result)

    def get_council(self, keypair: Keypair) -> list:
        """Return the list of council members."""
        result = self._read(self.governance, keypair, "council")
        raw = unwrap_plain(result)
        return raw if isinstance(raw, list) else []

    def is_council(self, keypair: Keypair, who: str) -> bool:
        """Check whether an account is a council member."""
        result = self._read(self.governance, keypair, "is_council", args={"who": who})
        return unwrap_plain(result)

    def get_governance_treasury(self, keypair: Keypair) -> str:
        """Return the treasury address from the governance contract."""
        result = self._read(self.governance, keypair, "treasury")
        return unwrap_plain(result)

    def get_governance_params(self, keypair: Keypair) -> dict:
        """Return the governance contract parameters."""
        result = self._read(self.governance, keypair, "params")
        raw = unwrap_plain(result)
        return raw if isinstance(raw, dict) else raw

    def get_current_epoch(self, keypair: Keypair) -> int:
        """Return the current epoch number."""
        result = self._read(self.governance, keypair, "current_epoch")
        return unwrap_plain(result)

    def get_snapshot(self, keypair: Keypair, epoch: int) -> dict | None:
        """Return the snapshot for a given epoch, or None."""
        result = self._read(self.governance, keypair, "get_snapshot", args={"epoch": epoch})
        return unwrap_option(result)

    def get_quorum(self, keypair: Keypair, epoch: int) -> tuple:
        """Return quorum data for an epoch as (yes, no) balance tuple."""
        result = self._read(self.governance, keypair, "quorum", args={"epoch": epoch})
        return unwrap_plain(result)

    def get_proposal_count(self, keypair: Keypair) -> int:
        """Return the total number of proposals."""
        result = self._read(self.governance, keypair, "proposal_count")
        return unwrap_plain(result)

    def get_proposal(self, keypair: Keypair, proposal_id: int) -> dict | None:
        """Return a proposal by ID, or None if not found."""
        result = self._read(self.governance, keypair, "get_proposal", args={"proposal_id": proposal_id})
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def has_voted(self, keypair: Keypair, proposal_id: int, coldkey: str, hotkey: str) -> bool:
        """Check whether a (coldkey, hotkey) pair has voted on a proposal."""
        result = self._read(
            self.governance,
            keypair,
            "has_voted",
            args={"proposal_id": proposal_id, "coldkey": coldkey, "hotkey": hotkey},
        )
        return unwrap_plain(result)

    # --- Mutating methods ---

    def set_council(self, keypair: Keypair, members: list) -> dict[str, Any] | DryRunResult:
        """Set the council member list (maintainer only)."""
        return self._exec(self.governance, keypair, "set_council", args={"members": members})

    def gov_vault_set_contract_params(
        self, keypair: Keypair, netuid: int, params: dict
    ) -> dict[str, Any] | DryRunResult:
        """Schedule a per-netuid vault contract parameter update via governance.

        Reads current on-chain params for *netuid* from the vault, merges
        with user-supplied changes, and sends the complete struct via the
        governance forwarder.
        """
        current = unwrap_plain(
            self._read(self.vault, keypair, "get_contract_params", args={"netuid": netuid})
        )
        if not isinstance(current, dict):
            raise ContractError(f"Expected dict from get_contract_params, got {type(current).__name__}")
        merged = dict(current)
        merged.update(params)
        return self._exec(
            self.governance,
            keypair,
            "vault_set_contract_params",
            args={"netuid": netuid, "params": merged},
        )

    def gov_vault_cancel_update(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Cancel a pending per-netuid vault contract parameter update via governance."""
        return self._exec(
            self.governance,
            keypair,
            "vault_cancel_contract_params_update",
            args={"netuid": netuid},
        )

    def gov_vault_claim_excess_alpha(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Claim excess alpha staking rewards on *netuid* via governance (maintainer only)."""
        return self._exec(self.governance, keypair, "vault_claim_excess_alpha", args={"netuid": netuid})

    def gov_get_vault_hotkey(self, keypair: Keypair) -> str:
        """Return the vault's staking hotkey address via governance."""
        result = self._read(self.governance, keypair, "vault_get_hotkey")
        return unwrap_plain(result)

    def gov_set_vault_hotkey(
        self, keypair: Keypair, new_hotkey: str, netuids: list[int]
    ) -> dict[str, Any] | DryRunResult:
        """Migrate the vault's staking hotkey via governance (maintainer only)."""
        return self._exec(
            self.governance,
            keypair,
            "vault_set_hotkey",
            args={"new_hotkey": new_hotkey, "netuids": netuids},
        )

    def gov_transfer_native_to_treasury(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Transfer the vault's native TAO to the treasury via governance (maintainer only)."""
        return self._exec(self.governance, keypair, "vault_transfer_native_to_treasury", args={})

    def gov_vault_set_approved_netuid(
        self, keypair: Keypair, netuid: int, approved: bool
    ) -> dict[str, Any] | DryRunResult:
        """Approve or revoke a subnet for vault collateral via governance (maintainer only)."""
        return self._exec(
            self.governance,
            keypair,
            "vault_set_approved_netuid",
            args={"netuid": netuid, "approved": approved},
        )

    def gov_vault_set_global_params(
        self, keypair: Keypair, config: dict[str, Any]
    ) -> dict[str, Any] | DryRunResult:
        """Schedule a vault global params update via governance (maintainer only)."""
        return self._exec(self.governance, keypair, "vault_set_global_params", args={"config": config})

    def gov_vault_cancel_global_params_update(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Cancel the pending vault global params update via governance (maintainer only)."""
        return self._exec(self.governance, keypair, "vault_cancel_global_params_update")

    def elect_maintainer(self, keypair: Keypair, new_maintainer: str) -> dict[str, Any] | DryRunResult:
        """Set the maintainer directly on the governance contract (election-only, selector 0xE1EC7000)."""
        return self._exec(
            self.governance,
            keypair,
            "elect_maintainer",
            args={"new_maintainer": new_maintainer},
        )

    def election_set_netuid(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Set the election contract netuid via governance (election-only, selector 0xE1EC7001)."""
        return self._exec(self.governance, keypair, "election_set_netuid", args={"netuid": netuid})

    def gov_vault_update_treasury(self, keypair: Keypair, new_treasury: str) -> dict[str, Any] | DryRunResult:
        """Update the vault treasury address via governance."""
        return self._exec(
            self.governance, keypair, "vault_update_treasury", args={"new_treasury": new_treasury}
        )

    def gov_vault_update_platform(self, keypair: Keypair, new_platform: str) -> dict[str, Any] | DryRunResult:
        """Update the vault platform address via governance."""
        return self._exec(
            self.governance, keypair, "vault_update_platform", args={"new_platform": new_platform}
        )

    # ---- Governance: vault upgrade / migration ----

    def gov_vault_set_token_controller(
        self, keypair: Keypair, new_controller: str
    ) -> dict[str, Any] | DryRunResult:
        """Transfer the ERC20 token controller via governance (maintainer only)."""
        return self._exec(
            self.governance, keypair, "vault_set_token_controller", args={"new_controller": new_controller}
        )

    def gov_vault_update_auction_address(
        self, keypair: Keypair, new_auction: str
    ) -> dict[str, Any] | DryRunResult:
        """Update the vault's auction contract address via governance (maintainer only)."""
        return self._exec(
            self.governance, keypair, "vault_update_auction_address", args={"new_auction": new_auction}
        )

    def gov_vault_update_oracle_address(
        self, keypair: Keypair, new_oracle: str
    ) -> dict[str, Any] | DryRunResult:
        """Update the vault's oracle contract address via governance (maintainer only)."""
        return self._exec(
            self.governance, keypair, "vault_update_oracle_address", args={"new_oracle": new_oracle}
        )

    # ---- Governance: own address management (maintainer only) ----

    def get_vault_address(self, keypair: Keypair) -> str:
        """Return the vault contract address from governance."""
        result = self._read(self.governance, keypair, "vault_address")
        return unwrap_plain(result)

    def get_governance_auction_address(self, keypair: Keypair) -> str:
        """Return the auction contract address from governance."""
        result = self._read(self.governance, keypair, "auction_address")
        return unwrap_plain(result)

    def get_governance_oracle_address(self, keypair: Keypair) -> str:
        """Return the oracle contract address from governance."""
        result = self._read(self.governance, keypair, "oracle_address")
        return unwrap_plain(result)

    def gov_update_vault_address(self, keypair: Keypair, new_vault: str) -> dict[str, Any] | DryRunResult:
        """Update the vault address in governance (maintainer only)."""
        return self._exec(self.governance, keypair, "update_vault_address", args={"new_vault": new_vault})

    def gov_update_auction_address(self, keypair: Keypair, new_auction: str) -> dict[str, Any] | DryRunResult:
        """Update the auction address in governance (maintainer only)."""
        return self._exec(
            self.governance, keypair, "update_auction_address", args={"new_auction": new_auction}
        )

    def gov_update_oracle_address(self, keypair: Keypair, new_oracle: str) -> dict[str, Any] | DryRunResult:
        """Update the oracle address in governance (maintainer only)."""
        return self._exec(self.governance, keypair, "update_oracle_address", args={"new_oracle": new_oracle})

    def gov_get_pool_address(self, keypair: Keypair) -> str:
        """Get the lending pool address from the governance contract."""
        result = self._read(self.governance, keypair, "pool_address")
        return unwrap_plain(result)

    def gov_update_pool_address(self, keypair: Keypair, new_pool: str) -> dict[str, Any] | DryRunResult:
        """Update the lending pool address in governance (maintainer only)."""
        return self._exec(self.governance, keypair, "update_pool_address", args={"new_pool": new_pool})

    def gov_update_treasury_address(
        self, keypair: Keypair, new_treasury: str
    ) -> dict[str, Any] | DryRunResult:
        """Update the treasury address in governance (maintainer only)."""
        return self._exec(
            self.governance, keypair, "update_treasury_address", args={"new_treasury": new_treasury}
        )

    def gov_vault_unpause(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Unpause the vault contract via governance."""
        return self._exec(self.governance, keypair, "vault_unpause")

    def gov_vault_pause(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Pause the vault contract via governance."""
        return self._exec(self.governance, keypair, "vault_pause")

    def gov_oracle_set_validator(
        self, keypair: Keypair, validator: str | None
    ) -> dict[str, Any] | DryRunResult:
        """Set the oracle validator via governance (pass None to clear)."""
        return self._exec(self.governance, keypair, "oracle_set_validator", args={"validator": validator})

    def gov_oracle_set_max_price_deviation(
        self, keypair: Keypair, max_price_deviation: int
    ) -> dict[str, Any] | DryRunResult:
        """Set the oracle max price deviation via governance."""
        return self._exec(
            self.governance,
            keypair,
            "oracle_set_max_price_deviation",
            args={"max_price_deviation": max_price_deviation},
        )

    def gov_oracle_commit_round(self, keypair: Keypair, price: int) -> dict[str, Any] | DryRunResult:
        """Commit the oracle round with an explicit price via governance."""
        return self._exec(self.governance, keypair, "oracle_commit_round", args={"price": price})

    def gov_oracle_set_netuid(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Set the oracle's governing subnet netuid via governance."""
        return self._exec(self.governance, keypair, "oracle_set_netuid", args={"netuid": netuid})

    def gov_oracle_set_min_submitter_stake(
        self, keypair: Keypair, min_stake: int
    ) -> dict[str, Any] | DryRunResult:
        """Set the oracle's minimum submitter stake via governance."""
        return self._exec(
            self.governance, keypair, "oracle_set_min_submitter_stake", args={"min_stake": min_stake}
        )

    def gov_auction_set_admin(self, keypair: Keypair, admin: str | None) -> dict[str, Any] | DryRunResult:
        """Set the auction admin via governance (pass None to clear)."""
        return self._exec(self.governance, keypair, "auction_set_admin", args={"admin": admin})

    def update_governance_params(
        self,
        keypair: Keypair,
        voting_period_ms: int,
        quorum_bps: int,
        approval_bps: int,
        min_proposer_stake: int,
        submission_open_day: int,
        submission_close_day: int,
    ) -> dict[str, Any] | DryRunResult:
        """Update governance parameters (maintainer only)."""
        args = {
            "new_params": {
                "voting_period_ms": voting_period_ms,
                "quorum_bps": quorum_bps,
                "approval_bps": approval_bps,
                "min_proposer_stake": min_proposer_stake,
                "submission_open_day": submission_open_day,
                "submission_close_day": submission_close_day,
            }
        }
        return self._exec(self.governance, keypair, "update_params", args)

    def submit_proposal(self, keypair: Keypair, cid: str, kind: dict) -> dict[str, Any] | DryRunResult:
        """Submit a new governance proposal (council only)."""
        return self._exec(
            self.governance,
            keypair,
            "submit_proposal",
            args={"cid": cid, "kind": kind},
        )

    def vote(
        self,
        keypair: Keypair,
        proposal_id: int,
        hotkey: str,
        support: bool,
        balance: int,
        multiplier_bps: int,
        proof: list,
    ) -> dict[str, Any] | DryRunResult:
        """Cast a vote on a governance proposal."""
        return self._exec(
            self.governance,
            keypair,
            "vote",
            args={
                "proposal_id": proposal_id,
                "hotkey": hotkey,
                "support": support,
                "balance": balance,
                "multiplier_bps": multiplier_bps,
                "proof": proof,
            },
        )

    def finalize_proposal(self, keypair: Keypair, proposal_id: int) -> dict[str, Any] | DryRunResult:
        """Finalize a governance proposal."""
        return self._exec(self.governance, keypair, "finalize", args={"proposal_id": proposal_id})

    def execute_proposal(self, keypair: Keypair, proposal_id: int) -> dict[str, Any] | DryRunResult:
        """Execute a finalized governance proposal."""
        return self._exec(self.governance, keypair, "execute", args={"proposal_id": proposal_id})

    def submit_snapshot(
        self,
        keypair: Keypair,
        root: list,
        circulating_supply: int,
        snapshot_block: int,
    ) -> dict[str, Any] | DryRunResult:
        """Submit a Merkle snapshot for a given block."""
        return self._exec(
            self.governance,
            keypair,
            "submit_snapshot",
            args={"root": root, "circulating_supply": circulating_supply, "snapshot_block": snapshot_block},
        )

    def get_netuid(self, keypair: Keypair) -> int:
        """Return the governing subnet netuid."""
        result = self._read(self.governance, keypair, "netuid")
        return unwrap_plain(result)

    def get_election_address(self, keypair: Keypair) -> str:
        """Return the election contract address registered in governance."""
        result = self._read(self.governance, keypair, "election")
        return unwrap_plain(result)

    def get_election_snapshot(self, keypair: Keypair):
        """Return the latest election snapshot, or None.

        Returns a 4-element list ``[merkle_root, circulating_supply, netuid,
        snapshot_block]`` when a snapshot exists, or ``None``.
        """
        result = self._read(self.governance, keypair, "election_snapshot")
        return unwrap_option(result)

    # ==================================================================
    # TOKEN (ERC-20) OPERATIONS
    # ==================================================================

    def balance_of(self, keypair: Keypair, owner: str) -> int:
        """Return the TUSDT token balance for *owner*."""
        result = self._read(self.token, keypair, "balance_of", args={"owner": owner})
        return unwrap_plain(result)

    def total_supply(self, keypair: Keypair) -> int:
        """Return the total TUSDT token supply."""
        result = self._read(self.token, keypair, "total_supply")
        return unwrap_plain(result)

    def allowance(self, keypair: Keypair, owner: str, spender: str) -> int:
        """Return the token allowance *spender* may spend on behalf of *owner*."""
        result = self._read(self.token, keypair, "allowance", args={"owner": owner, "spender": spender})
        return unwrap_plain(result)

    def approve(self, keypair: Keypair, spender: str, amount: int) -> dict[str, Any] | DryRunResult:
        """Approve *spender* to spend *amount* TUSDT tokens."""
        return self._exec(self.token, keypair, "approve", args={"spender": spender, "value": amount})

    def transfer(self, keypair: Keypair, to: str, amount: int) -> dict[str, Any] | DryRunResult:
        """Transfer *amount* TUSDT tokens to *to*."""
        return self._exec(self.token, keypair, "transfer", args={"to": to, "value": amount})

    def token_controller(self, keypair: Keypair) -> str:
        """Return the controller address of the TUSDT token contract."""
        result = self._read(self.token, keypair, "controller")
        return unwrap_plain(result)

    def set_controller(self, keypair: Keypair, new_controller: str) -> dict[str, Any] | DryRunResult:
        """Transfer the token controller role to *new_controller* (controller only)."""
        return self._exec(self.token, keypair, "set_controller", args={"new_controller": new_controller})

    def add_minter(self, keypair: Keypair, minter: str) -> dict[str, Any] | DryRunResult:
        """Authorize *minter* to mint and burn tokens (controller only)."""
        return self._exec(self.token, keypair, "add_minter", args={"minter": minter})

    def remove_minter(self, keypair: Keypair, minter: str) -> dict[str, Any] | DryRunResult:
        """Revoke mint/burn authorization from *minter* (controller only)."""
        return self._exec(self.token, keypair, "remove_minter", args={"minter": minter})

    def is_minter(self, keypair: Keypair, account: str) -> bool:
        """Return whether *account* is an authorized minter."""
        result = self._read(self.token, keypair, "is_minter", args={"account": account})
        return unwrap_plain(result)

    def token_mint(self, keypair: Keypair, to: str, amount: int) -> dict[str, Any] | DryRunResult:
        """Mint *amount* TUSDT tokens to *to* (minter only)."""
        return self._exec(self.token, keypair, "mint", args={"to": to, "value": amount})

    def token_burn(self, keypair: Keypair, from_addr: str, amount: int) -> dict[str, Any] | DryRunResult:
        """Burn *amount* TUSDT tokens from *from_addr* (minter only)."""
        return self._exec(self.token, keypair, "burn", args={"from": from_addr, "value": amount})

    def token_increase_allowance(
        self, keypair: Keypair, spender: str, delta: int
    ) -> dict[str, Any] | DryRunResult:
        """Increase *spender*'s allowance by *delta* TUSDT tokens."""
        return self._exec(
            self.token, keypair, "increase_allowance", args={"spender": spender, "delta_value": delta}
        )

    def token_decrease_allowance(
        self, keypair: Keypair, spender: str, delta: int
    ) -> dict[str, Any] | DryRunResult:
        """Decrease *spender*'s allowance by *delta* TUSDT tokens."""
        return self._exec(
            self.token, keypair, "decrease_allowance", args={"spender": spender, "delta_value": delta}
        )

    def token_transfer_from(
        self, keypair: Keypair, from_addr: str, to: str, amount: int
    ) -> dict[str, Any] | DryRunResult:
        """Transfer *amount* TUSDT tokens from *from_addr* to *to* (requires allowance)."""
        return self._exec(
            self.token, keypair, "transfer_from", args={"from": from_addr, "to": to, "value": amount}
        )

    # ==================================================================
    # AUCTION OPERATIONS
    # ==================================================================

    def list_active_auctions(self, keypair: Keypair, page: int = 0) -> list[dict]:
        """Return a page of active auctions."""
        result = self._read(self.auction, keypair, "get_active_auctions", args={"page": page})
        auctions = unwrap_result(result)
        if isinstance(auctions, list):
            return auctions
        return []

    def get_active_auctions_count(self, keypair: Keypair) -> int:
        """Return the number of currently active auctions."""
        result = self._read(self.auction, keypair, "get_active_auctions_count")
        return unwrap_plain(result)

    def get_auction(self, keypair: Keypair, auction_id: int) -> dict | None:
        """Query a single auction by ID."""
        result = self._read(self.auction, keypair, "get_auction", args={"auction_id": auction_id})
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def place_bid(
        self,
        keypair: Keypair,
        auction_id: int,
        amount: int,
        hot_key: str | None = None,
    ) -> dict[str, Any] | DryRunResult:
        """Place a bid on an auction."""
        args: dict[str, Any] = {
            "auction_id": auction_id,
            "bid_amount": amount,
        }
        if hot_key:
            args["metadata"] = {"hot_key": hot_key}
        else:
            args["metadata"] = None
        return self._exec(self.auction, keypair, "place_bid", args=args)

    def finalize_auction(self, keypair: Keypair, auction_id: int) -> dict[str, Any] | DryRunResult:
        """Finalize an auction after its end time."""
        return self._exec(self.auction, keypair, "finalize_auction", args={"auction_id": auction_id})

    def withdraw_refund(
        self, keypair: Keypair, auction_id: int, bid_id: int
    ) -> dict[str, Any] | DryRunResult:
        """Withdraw a refund for a non-winning bid after auction finalization."""
        return self._exec(
            self.auction, keypair, "withdraw_refund", args={"auction_id": auction_id, "bid_id": bid_id}
        )

    def get_my_bid(self, keypair: Keypair, auction_id: int, bidder: str) -> dict | None:
        """Get the caller's bid in an auction."""
        result = self._read(
            self.auction, keypair, "get_auction_bid", args={"auction_id": auction_id, "bidder": bidder}
        )
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def list_all_auctions(self, keypair: Keypair, page: int = 0) -> list[dict]:
        """Return a page of all auctions (active + finalized)."""
        result = self._read(self.auction, keypair, "get_all_auctions", args={"page": page})
        auctions = unwrap_result(result)
        if isinstance(auctions, list):
            return auctions
        return []

    def get_total_auctions_count(self, keypair: Keypair) -> int:
        """Return the total number of auctions."""
        result = self._read(self.auction, keypair, "get_total_auctions_count")
        return unwrap_plain(result)

    def get_active_vault_auction(self, keypair: Keypair, vault_owner: str, vault_id: int) -> int | None:
        """Return the active auction ID for a specific vault, or ``None``."""
        result = self._read(
            self.auction,
            keypair,
            "get_active_vault_auction",
            args={"vault_owner": vault_owner, "vault_id": vault_id},
        )
        return unwrap_option(result)

    def list_bids(self, keypair: Keypair, auction_id: int, page: int = 0) -> list[dict]:
        """Return a page of bids for an auction."""
        result = self._read(self.auction, keypair, "get_bids", args={"auction_id": auction_id, "page": page})
        bids = unwrap_result(result)
        if isinstance(bids, list):
            return bids
        return []

    def get_bid(self, keypair: Keypair, auction_id: int, bid_id: int) -> dict | None:
        """Get a specific bid by auction ID and bid ID."""
        result = self._read(
            self.auction, keypair, "get_bid", args={"auction_id": auction_id, "bid_id": bid_id}
        )
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def get_auction_controller(self, keypair: Keypair) -> str:
        """Return the auction controller address."""
        result = self._read(self.auction, keypair, "controller")
        return unwrap_plain(result)

    def get_auction_governance(self, keypair: Keypair) -> str:
        """Return the auction governance address."""
        result = self._read(self.auction, keypair, "governance")
        return unwrap_plain(result)

    def get_auction_admin(self, keypair: Keypair) -> str | None:
        """Return the auction admin address, or None if not set."""
        result = self._read(self.auction, keypair, "admin")
        return unwrap_option(result)

    def auction_set_controller(self, keypair: Keypair, new_controller: str) -> dict[str, Any] | DryRunResult:
        """Transfer the auction controller role to a new vault (governance only)."""
        return self._exec(self.auction, keypair, "set_controller", args={"new_controller": new_controller})

    def create_auction(
        self,
        keypair: Keypair,
        vault_owner: str,
        vault_id: int,
        collateral_balance: int,
        debt_balance: int,
        min_bid: int,
        liquidation_price: int,
        duration_ms: int | None = None,
    ) -> dict[str, Any] | DryRunResult:
        """Create a new liquidation auction (controller only)."""
        return self._exec(
            self.auction,
            keypair,
            "create_auction",
            args={
                "vault_owner": vault_owner,
                "vault_id": vault_id,
                "collateral_balance": collateral_balance,
                "debt_balance": debt_balance,
                "min_bid": min_bid,
                "liquidation_price": liquidation_price,
                "duration_ms": duration_ms,
            },
        )

    def auction_set_admin(self, keypair: Keypair, admin: str | None) -> dict[str, Any] | DryRunResult:
        """Set or clear the auction admin (governance only). Pass None to clear."""
        return self._exec(self.auction, keypair, "set_admin", args={"admin": admin})

    def auction_update_governance(
        self, keypair: Keypair, new_governance: str
    ) -> dict[str, Any] | DryRunResult:
        """Transfer auction governance to a new account (controller only)."""
        return self._exec(self.auction, keypair, "update_governance", args={"new_governance": new_governance})

    def auction_transfer_winning_bid(
        self,
        keypair: Keypair,
        auction_id: int,
        recipient: str,
    ) -> dict[str, Any] | DryRunResult:
        """Transfer the winning bid amount to a recipient (controller only)."""
        return self._exec(
            self.auction,
            keypair,
            "transfer_winning_bid",
            args={"auction_id": auction_id, "recipient": recipient},
        )

    # ==================================================================
    # ORACLE OPERATIONS
    # ==================================================================

    def get_latest_price(self, keypair: Keypair) -> dict | None:
        """Return the latest committed oracle price data."""
        result = self._read(self.oracle, keypair, "get_latest_price")
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def get_current_round(self, keypair: Keypair) -> int:
        """Return the current oracle round ID."""
        result = self._read(self.oracle, keypair, "current_round_id")
        return unwrap_plain(result)

    def submit_price(
        self, keypair: Keypair, price: int, hot_key: str, provider: str | None = None
    ) -> dict[str, Any] | DryRunResult:
        """Submit a price to the oracle. The caller must be a registered subnet neuron."""
        provider_bytes = provider.encode() if provider else None
        args: dict[str, Any] = {
            "price": price,
            "metadata": {"hot_key": hot_key, "provider": provider_bytes},
        }
        return self._exec(self.oracle, keypair, "submit_price", args=args)

    def commit_round(
        self, keypair: Keypair, override_price: int | None = None
    ) -> dict[str, Any] | DryRunResult:
        """Commit the current oracle round. Optionally override the median price."""
        args: dict[str, Any] = {"override_price": override_price}
        return self._exec(self.oracle, keypair, "commit_round", args=args)

    def get_round_price(self, keypair: Keypair, round_id: int) -> dict | None:
        """Return the price data for a specific round."""
        result = self._read(self.oracle, keypair, "get_round_price", args={"round_id": round_id})
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def get_price_history(self, keypair: Keypair, page: int = 0) -> list:
        """Return a page of price history."""
        result = self._read(self.oracle, keypair, "get_price_history", args={"page": page})
        raw = unwrap_plain(result)
        if isinstance(raw, list):
            return raw
        return []

    def get_price_history_count(self, keypair: Keypair) -> int:
        """Return the total number of price history entries."""
        result = self._read(self.oracle, keypair, "get_price_history_count")
        return unwrap_plain(result)

    def get_round_submissions(self, keypair: Keypair, round_id: int) -> list:
        """Return all submissions for a specific round."""
        result = self._read(self.oracle, keypair, "get_round_submissions", args={"round_id": round_id})
        raw = unwrap_plain(result)
        if isinstance(raw, list):
            return raw
        return []

    def get_current_round_summary(self, keypair: Keypair) -> dict:
        """Return a summary of the current oracle round."""
        result = self._read(self.oracle, keypair, "get_current_round_summary")
        raw = unwrap_plain(result)
        return raw if isinstance(raw, dict) else raw

    def get_oracle_controller(self, keypair: Keypair) -> str:
        """Return the oracle controller account address."""
        result = self._read(self.oracle, keypair, "controller")
        return unwrap_plain(result)

    def get_oracle_governance(self, keypair: Keypair) -> str:
        """Return the oracle contract's governance address."""
        result = self._read(self.oracle, keypair, "governance")
        return str(unwrap_plain(result))

    def get_oracle_validator(self, keypair: Keypair) -> str | None:
        """Return the oracle validator account, or None if not set."""
        result = self._read(self.oracle, keypair, "validator")
        return unwrap_option(result)

    def get_max_price_deviation(self, keypair: Keypair) -> int:
        """Return the current max price deviation ratio (10^18 scale)."""
        result = self._read(self.oracle, keypair, "max_price_deviation")
        return unwrap_plain(result)

    def get_max_round_submissions(self, keypair: Keypair) -> int:
        """Return the maximum number of submissions allowed per round."""
        result = self._read(self.oracle, keypair, "max_round_submissions")
        return unwrap_plain(result)

    def commit_round_governance(self, keypair: Keypair, price: int) -> dict[str, Any] | DryRunResult:
        """Governance commits the current oracle round with an explicit price."""
        return self._exec(self.oracle, keypair, "commit_round_governance", args={"price": price})

    def oracle_get_netuid(self, keypair: Keypair) -> int:
        """Return the oracle's governing subnet netuid."""
        result = self._read(self.oracle, keypair, "get_netuid")
        return unwrap_plain(result)

    def oracle_set_netuid(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Set the oracle's governing subnet netuid (governance only)."""
        return self._exec(self.oracle, keypair, "set_netuid", args={"netuid": netuid})

    def oracle_get_min_submitter_stake(self, keypair: Keypair) -> int:
        """Return the oracle's minimum required submitter stake."""
        result = self._read(self.oracle, keypair, "min_submitter_stake")
        return unwrap_plain(result)

    def oracle_set_min_submitter_stake(
        self, keypair: Keypair, min_stake: int
    ) -> dict[str, Any] | DryRunResult:
        """Set the oracle's minimum submitter stake (governance only)."""
        return self._exec(self.oracle, keypair, "set_min_submitter_stake", args={"min_stake": min_stake})

    def set_validator(self, keypair: Keypair, validator: str | None) -> dict[str, Any] | DryRunResult:
        """Set the oracle validator account (governance only). Pass None to clear."""
        return self._exec(self.oracle, keypair, "set_validator", args={"validator": validator})

    def set_max_price_deviation(
        self, keypair: Keypair, max_price_deviation: int
    ) -> dict[str, Any] | DryRunResult:
        """Set the maximum allowed price deviation between rounds (governance only)."""
        return self._exec(
            self.oracle,
            keypair,
            "set_max_price_deviation",
            args={"max_price_deviation": max_price_deviation},
        )

    def oracle_update_governance(
        self, keypair: Keypair, new_governance: str
    ) -> dict[str, Any] | DryRunResult:
        """Transfer oracle governance to a new account (controller only)."""
        return self._exec(self.oracle, keypair, "update_governance", args={"new_governance": new_governance})

    def oracle_set_controller(self, keypair: Keypair, new_controller: str) -> dict[str, Any] | DryRunResult:
        """Transfer the oracle controller role to a new vault (governance only)."""
        return self._exec(self.oracle, keypair, "set_controller", args={"new_controller": new_controller})

    # ==================================================================
    # TREASURY OPERATIONS
    # ==================================================================

    def treasury_get_governance(self, keypair: Keypair) -> str:
        """Return the governance address from the treasury contract."""
        result = self._read(self.treasury, keypair, "governance")
        return unwrap_plain(result)

    def treasury_get_token(self, keypair: Keypair) -> str:
        """Return the TUSDT token address from the treasury contract."""
        result = self._read(self.treasury, keypair, "token")
        return unwrap_plain(result)

    def treasury_fund_balance_tusdt(self, keypair: Keypair, fund: dict) -> int:
        """Return the TUSDT balance for a specific fund."""
        result = self._read(self.treasury, keypair, "fund_balance_tusdt", args={"fund": fund})
        return unwrap_plain(result)

    def treasury_fund_balance_native(self, keypair: Keypair, fund: dict) -> int:
        """Return the native balance for a specific fund."""
        result = self._read(self.treasury, keypair, "fund_balance_native", args={"fund": fund})
        return unwrap_plain(result)

    def treasury_pending_tusdt(self, keypair: Keypair) -> int:
        """Return the total pending TUSDT balance."""
        result = self._read(self.treasury, keypair, "pending_tusdt")
        return unwrap_plain(result)

    def treasury_pending_native(self, keypair: Keypair) -> int:
        """Return the total pending native balance."""
        result = self._read(self.treasury, keypair, "pending_native")
        return unwrap_plain(result)

    def treasury_set_governance(self, keypair: Keypair, new_governance: str) -> dict[str, Any] | DryRunResult:
        """Set a new governance address for the treasury (governance only)."""
        return self._exec(self.treasury, keypair, "set_governance", args={"new_governance": new_governance})

    def treasury_distribute(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Distribute pending funds to their respective fund balances."""
        return self._exec(self.treasury, keypair, "distribute")

    def treasury_release(
        self,
        keypair: Keypair,
        fund: dict,
        token_kind: dict,
        amount: int,
        recipient: str,
    ) -> dict[str, Any] | DryRunResult:
        """Release funds from a specific fund to a recipient (governance only)."""
        return self._exec(
            self.treasury,
            keypair,
            "release",
            args={"fund": fund, "token_kind": token_kind, "amount": amount, "recipient": recipient},
        )

    # ==================================================================
    # ELECTION OPERATIONS
    # ==================================================================

    # --- Read methods ---

    def get_election_governance(self, keypair: Keypair) -> str:
        """Return the governance address from the election contract."""
        result = self._read(self.election, keypair, "governance")
        return unwrap_plain(result)

    def get_min_candidate_stake(self, keypair: Keypair) -> int:
        """Return the minimum candidate stake (alpha)."""
        result = self._read(self.election, keypair, "min_candidate_stake")
        return unwrap_plain(result)

    def get_incumbent(self, keypair: Keypair) -> str:
        """Return the current incumbent maintainer address."""
        result = self._read(self.election, keypair, "incumbent")
        return unwrap_plain(result)

    def get_active_netuid(self, keypair: Keypair) -> int:
        """Return the active governing subnet netuid."""
        result = self._read(self.election, keypair, "active_netuid")
        return unwrap_plain(result)

    def get_phase(self, keypair: Keypair):
        """Return the current election phase.

        Returns a dict e.g. ``{"Idle": null}`` or a string ``"Idle"``.
        """
        result = self._read(self.election, keypair, "phase")
        return unwrap_plain(result)

    def get_cycle_id(self, keypair: Keypair) -> int:
        """Return the current election cycle ID."""
        result = self._read(self.election, keypair, "cycle_id")
        return unwrap_plain(result)

    def get_next_election_ts(self, keypair: Keypair) -> int:
        """Return the earliest timestamp when the next election may be scheduled."""
        result = self._read(self.election, keypair, "next_election_ts")
        return unwrap_plain(result)

    def get_terms_served(self, keypair: Keypair, who: str) -> int:
        """Return the number of terms served by an account."""
        result = self._read(self.election, keypair, "terms_served", args={"who": who})
        return unwrap_plain(result)

    def get_candidate(self, keypair: Keypair, candidate: str) -> dict | None:
        """Return a candidate's registration info, or None."""
        result = self._read(self.election, keypair, "get_candidate", args={"candidate": candidate})
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def get_candidate_list(self, keypair: Keypair) -> list:
        """Return the ordered list of registered candidate addresses."""
        result = self._read(self.election, keypair, "candidate_list")
        raw = unwrap_plain(result)
        return raw if isinstance(raw, list) else []

    def get_approval_weight(self, keypair: Keypair, candidate: str) -> int:
        """Return the accumulated approval weight for a candidate."""
        result = self._read(self.election, keypair, "approval_weight", args={"candidate": candidate})
        return unwrap_plain(result)

    def get_total_participating_power(self, keypair: Keypair) -> int:
        """Return the total summed voting power of all participants."""
        result = self._read(self.election, keypair, "total_participating_power")
        return unwrap_plain(result)

    def get_total_voted_balance(self, keypair: Keypair) -> int:
        """Return the total raw alpha balance of all participants."""
        result = self._read(self.election, keypair, "total_voted_balance")
        return unwrap_plain(result)

    def get_quorum_election(self, keypair: Keypair) -> int:
        """Return the quorum threshold for the current election cycle."""
        result = self._read(self.election, keypair, "quorum")
        return unwrap_plain(result)

    def get_leading_candidate(self, keypair: Keypair):
        """Return the leading candidate as ``(address, weight)``, or None."""
        result = self._read(self.election, keypair, "leading_candidate")
        return unwrap_option(result)

    def get_maintainer_elect(self, keypair: Keypair) -> dict | None:
        """Return the maintainer-elect info, or None."""
        result = self._read(self.election, keypair, "maintainer_elect")
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def get_transition(self, keypair: Keypair) -> dict | None:
        """Return the active subnet transition info, or None."""
        result = self._read(self.election, keypair, "transition")
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def is_in_transition(self, keypair: Keypair) -> bool:
        """Return whether a subnet transition is active."""
        result = self._read(self.election, keypair, "is_in_transition")
        return unwrap_plain(result)

    def get_voting_window(self, keypair: Keypair):
        """Return the voting window as ``(opens_at, ends_at)``."""
        result = self._read(self.election, keypair, "voting_window")
        return unwrap_plain(result)

    # --- Write (mutating) methods ---

    def schedule_election(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Schedule a new election cycle (permissionless)."""
        return self._exec(self.election, keypair, "schedule_election")

    def register_candidate(self, keypair: Keypair, netuid: int, hotkey: str) -> dict[str, Any] | DryRunResult:
        """Register as a candidate for the current election cycle."""
        return self._exec(
            self.election, keypair, "register_candidate", args={"netuid": netuid, "hotkey": hotkey}
        )

    def cast_approval(
        self,
        keypair: Keypair,
        candidate: str,
        hotkey: str,
        balance: int,
        multiplier_bps: int,
        proof: list,
    ) -> dict[str, Any] | DryRunResult:
        """Cast an approval vote for a candidate."""
        return self._exec(
            self.election,
            keypair,
            "cast_approval",
            args={
                "candidate": candidate,
                "hotkey": hotkey,
                "balance": balance,
                "multiplier_bps": multiplier_bps,
                "proof": proof,
            },
        )

    def finalize_election(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Finalize the current election cycle (permissionless)."""
        return self._exec(self.election, keypair, "finalize")

    def activate_election(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Activate the elected maintainer (permissionless)."""
        return self._exec(self.election, keypair, "activate")

    def end_transition(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """End the active subnet transition (permissionless)."""
        return self._exec(self.election, keypair, "end_transition")

    def trigger_emergency_election(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Trigger an emergency election (incumbent only)."""
        return self._exec(self.election, keypair, "trigger_emergency_election")

    def cancel_cycle(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Cancel the current election cycle (incumbent only)."""
        return self._exec(self.election, keypair, "cancel_cycle")

    # ==================================================================
    # Lending pool — supply / withdraw
    # ==================================================================

    def lending_supply_tao(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Supply native TAO to the lending pool, receiving lTAO."""
        return self._exec(
            self.lending,
            keypair,
            "supply_tao",
            args={"amount": amount},
            value=amount,
        )

    def lending_supply_tusdt(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Supply TUSDT to the lending pool, receiving lTUSDT. Requires pre-approval."""
        return self._exec(
            self.lending,
            keypair,
            "supply_tusdt",
            args={"amount": amount},
        )

    def lending_withdraw_tao(self, keypair: Keypair, ltoken_amount: int) -> dict[str, Any] | DryRunResult:
        """Withdraw native TAO from the lending pool by burning lTAO."""
        return self._exec(
            self.lending,
            keypair,
            "withdraw_tao",
            args={"ltoken_amount": ltoken_amount},
        )

    def lending_withdraw_tusdt(self, keypair: Keypair, ltoken_amount: int) -> dict[str, Any] | DryRunResult:
        """Withdraw TUSDT from the lending pool by burning lTUSDT."""
        return self._exec(
            self.lending,
            keypair,
            "withdraw_tusdt",
            args={"ltoken_amount": ltoken_amount},
        )

    # ==================================================================
    # Lending pool — borrow / repay
    # ==================================================================

    def lending_borrow_tao(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Borrow native TAO against alpha collateral."""
        return self._exec(
            self.lending,
            keypair,
            "borrow_tao",
            args={"amount": amount},
        )

    def lending_borrow_tusdt(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Borrow TUSDT against alpha collateral."""
        return self._exec(
            self.lending,
            keypair,
            "borrow_tusdt",
            args={"amount": amount},
        )

    def lending_repay_tao(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Repay a native TAO loan. Attach native TAO via value=amount."""
        return self._exec(
            self.lending,
            keypair,
            "repay_tao",
            args={"amount": amount},
            value=amount,
        )

    def lending_repay_tusdt(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Repay a TUSDT loan. Requires pre-approval."""
        return self._exec(
            self.lending,
            keypair,
            "repay_tusdt",
            args={"amount": amount},
        )

    def lending_accrue_market_interest(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Accrue interest for both debt markets (permissionless).

        Refreshes each market's borrow index, exchange rate, and reserve
        against the time elapsed since its last accrual.
        """
        return self._exec(
            self.lending,
            keypair,
            "accrue_market_interest",
            args={},
        )

    # ==================================================================
    # Lending pool — alpha collateral
    # ==================================================================

    def lending_deposit_alpha(
        self, keypair: Keypair, netuid: int, amount: int
    ) -> dict[str, Any] | DryRunResult:
        """Deposit alpha stake as collateral into the lending pool."""
        return self._exec(
            self.lending,
            keypair,
            "deposit_alpha",
            args={"netuid": netuid, "amount": amount},
        )

    def lending_withdraw_alpha(
        self, keypair: Keypair, netuid: int, amount: int, dest_coldkey: str
    ) -> dict[str, Any] | DryRunResult:
        """Withdraw alpha collateral from the lending pool."""
        return self._exec(
            self.lending,
            keypair,
            "withdraw_alpha",
            args={"netuid": netuid, "amount": amount, "dest_coldkey": dest_coldkey},
        )

    # ==================================================================
    # Lending pool — liquidation
    # ==================================================================

    def lending_liquidate(
        self,
        keypair: Keypair,
        borrower: str,
        value: int = 0,
    ) -> dict[str, Any] | DryRunResult:
        """Liquidate an underwater borrower (full-seizure).

        The borrower's full debt on both markets is repaid — TAO via the
        attached native ``value`` and TUSDT via ``transfer_from`` — and all
        of the borrower's alpha collateral is seized, minus the platform's
        liquidation fee.
        """
        return self._exec(
            self.lending,
            keypair,
            "liquidate",
            args={"borrower": borrower},
            value=value,
        )

    # ==================================================================
    # Lending pool — permissionless claims
    # ==================================================================

    def lending_claim_alpha_excess(self, keypair: Keypair, netuid: int) -> dict[str, Any] | DryRunResult:
        """Claim excess alpha staking for a netuid (permissionless). Unstakes
        the full excess (available stake minus booked principal) and sends the
        TAO to the treasury."""
        return self._exec(
            self.lending,
            keypair,
            "claim_alpha_excess",
            args={"netuid": netuid},
        )

    def lending_claim_reserve(self, keypair: Keypair, market_id: int) -> dict[str, Any] | DryRunResult:
        """Claim accrued protocol reserve for a market (permissionless)."""
        return self._exec(
            self.lending,
            keypair,
            "claim_reserve",
            args={"market_id": market_id},
        )

    # ==================================================================
    # Lending pool — governance: alpha market management
    # ==================================================================

    def lending_set_approved_netuid(
        self, keypair: Keypair, netuid: int, approved: bool
    ) -> dict[str, Any] | DryRunResult:
        """Approve or revoke a subnet for alpha collateral."""
        return self._exec(
            self.lending,
            keypair,
            "set_approved_netuid",
            args={"netuid": netuid, "approved": approved},
        )

    def lending_set_alpha_params(
        self, keypair: Keypair, netuid: int, config: dict[str, Any]
    ) -> dict[str, Any] | DryRunResult:
        """Schedule an alpha market params update (60s timelock)."""
        return self._exec(
            self.lending,
            keypair,
            "set_alpha_params",
            args={"netuid": netuid, "config": config},
        )

    def lending_execute_alpha_params_update(
        self, keypair: Keypair, netuid: int
    ) -> dict[str, Any] | DryRunResult:
        """Execute a pending alpha params update (permissionless, time-gated)."""
        return self._exec(
            self.lending,
            keypair,
            "execute_alpha_params_update",
            args={"netuid": netuid},
        )

    def lending_cancel_alpha_params_update(
        self, keypair: Keypair, netuid: int
    ) -> dict[str, Any] | DryRunResult:
        """Cancel a pending alpha params update."""
        return self._exec(
            self.lending,
            keypair,
            "cancel_alpha_params_update",
            args={"netuid": netuid},
        )

    # ==================================================================
    # Lending pool — governance: interest rate params
    # ==================================================================

    def lending_set_market_params(
        self, keypair: Keypair, market_id: int, config: dict[str, Any]
    ) -> dict[str, Any] | DryRunResult:
        """Schedule an interest rate params update for a market (60s timelock)."""
        return self._exec(
            self.lending,
            keypair,
            "set_market_params",
            args={"market_id": market_id, "config": config},
        )

    def lending_execute_market_params_update(
        self, keypair: Keypair, market_id: int
    ) -> dict[str, Any] | DryRunResult:
        """Execute a pending market params update (permissionless, time-gated)."""
        return self._exec(
            self.lending,
            keypair,
            "execute_market_params_update",
            args={"market_id": market_id},
        )

    def lending_cancel_market_params_update(
        self, keypair: Keypair, market_id: int
    ) -> dict[str, Any] | DryRunResult:
        """Cancel a pending market params update."""
        return self._exec(
            self.lending,
            keypair,
            "cancel_market_params_update",
            args={"market_id": market_id},
        )

    # ==================================================================
    # Lending pool — governance: global params
    # ==================================================================

    def lending_set_global_params(
        self, keypair: Keypair, config: dict[str, Any]
    ) -> dict[str, Any] | DryRunResult:
        """Schedule a global params update (60s timelock)."""
        return self._exec(
            self.lending,
            keypair,
            "set_global_params",
            args={"config": config},
        )

    def lending_execute_global_params_update(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Execute a pending global params update (permissionless, time-gated)."""
        return self._exec(
            self.lending,
            keypair,
            "execute_global_params_update",
        )

    def lending_cancel_global_params_update(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Cancel a pending global params update."""
        return self._exec(
            self.lending,
            keypair,
            "cancel_global_params_update",
        )

    # ==================================================================
    # Lending pool — governance: roles & addresses
    # ==================================================================

    def lending_update_governance(
        self, keypair: Keypair, new_governance: str
    ) -> dict[str, Any] | DryRunResult:
        """Transfer the lending pool governance role."""
        return self._exec(
            self.lending,
            keypair,
            "update_governance",
            args={"new_governance": new_governance},
        )

    def lending_update_treasury(self, keypair: Keypair, new_treasury: str) -> dict[str, Any] | DryRunResult:
        """Update the lending pool treasury address."""
        return self._exec(
            self.lending,
            keypair,
            "update_treasury",
            args={"new_treasury": new_treasury},
        )

    def lending_update_platform(self, keypair: Keypair, new_platform: str) -> dict[str, Any] | DryRunResult:
        """Update the lending pool platform (pause operator) address."""
        return self._exec(
            self.lending,
            keypair,
            "update_platform",
            args={"new_platform": new_platform},
        )

    def lending_update_oracle_address(
        self, keypair: Keypair, new_oracle: str
    ) -> dict[str, Any] | DryRunResult:
        """Update the lending pool oracle address."""
        return self._exec(
            self.lending,
            keypair,
            "update_oracle_address",
            args={"new_oracle": new_oracle},
        )

    def lending_update_ltoken_address(
        self, keypair: Keypair, market_id: int, new_ltoken: str
    ) -> dict[str, Any] | DryRunResult:
        """Update an lToken child contract address."""
        return self._exec(
            self.lending,
            keypair,
            "update_ltoken_address",
            args={"market_id": market_id, "new_ltoken": new_ltoken},
        )

    def lending_update_pool_hotkey(
        self, keypair: Keypair, new_hotkey: str, netuids: list[int]
    ) -> dict[str, Any] | DryRunResult:
        """Migrate all alpha stake to a new pool hotkey."""
        return self._exec(
            self.lending,
            keypair,
            "update_pool_hotkey",
            args={"new_hotkey": new_hotkey, "netuids": netuids},
        )

    def lending_claim_surplus_tusdt(self, keypair: Keypair, amount: int) -> dict[str, Any] | DryRunResult:
        """Claim surplus TUSDT held by the lending pool to the treasury."""
        return self._exec(
            self.lending,
            keypair,
            "claim_surplus_tusdt",
            args={"amount": amount},
        )

    # ==================================================================
    # Lending pool — emergency pause
    # ==================================================================

    def lending_pause(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Pause the lending pool (governance or platform)."""
        return self._exec(self.lending, keypair, "pause")

    def lending_unpause(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Unpause the lending pool (governance only)."""
        return self._exec(self.lending, keypair, "unpause")

    # ==================================================================
    # Lending pool — native sweep
    # ==================================================================

    def lending_transfer_native_to_treasury(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Sweep native TAO balance of the lending pool to the treasury."""
        return self._exec(self.lending, keypair, "transfer_native_to_treasury")

    # ==================================================================
    # Lending pool — idle-TAO root staking
    # ==================================================================

    def lending_set_root_stake_config(
        self,
        keypair: Keypair,
        root_hotkey: str,
        staking_enabled: bool,
        stake_buffer: int,
        sweep_threshold: int,
        stake_floor: int,
    ) -> dict[str, Any] | DryRunResult:
        """Update the idle-TAO root-subnet staking configuration (governance-gated).

        ``staking_enabled`` is an off-switch (default false).  ``sweep`` stakes
        only the excess above ``stake_buffer + sweep_threshold`` and always
        keeps ``stake_floor`` liquid.  The contract enforces
        ``stake_floor >= 2_000_000`` rao and ``stake_buffer >= stake_floor``;
        rotating the hotkey with stake outstanding fully unstakes first.
        """
        return self._exec(
            self.lending,
            keypair,
            "set_root_stake_config",
            args={
                "root_hotkey": root_hotkey,
                "staking_enabled": staking_enabled,
                "stake_buffer": stake_buffer,
                "sweep_threshold": sweep_threshold,
                "stake_floor": stake_floor,
            },
        )

    def lending_sweep(self, keypair: Keypair) -> dict[str, Any] | DryRunResult:
        """Stake excess idle TAO into the root subnet (permissionless keeper call).

        No-op when staking is disabled, the pool is paused, the excess is
        below ``stake_floor``, or a sweep already ran this block.
        """
        return self._exec(
            self.lending,
            keypair,
            "sweep",
            args={},
        )

    # ==================================================================
    # Lending pool — queries / getters
    # ==================================================================

    def lending_get_market_state(self, keypair: Keypair, market_id: int) -> dict | None:
        """Get market state for a lending market."""
        result = self._read(self.lending, keypair, "get_market_state", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_market_deficit(self, keypair: Keypair, market_id: int) -> int | None:
        """Get a market's frozen bad-debt deficit (face units), or None when nothing is booked."""
        result = self._read(self.lending, keypair, "get_market_deficit", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_position(self, keypair: Keypair, market_id: int, user: str) -> dict | None:
        """Get a user's position in a lending market."""
        result = self._read(
            self.lending, keypair, "get_position", args={"market_id": market_id, "user": user}
        )
        return unwrap_option(result)

    def lending_get_exchange_rate(self, keypair: Keypair, market_id: int) -> int | None:
        """Get lToken exchange rate for a market (1e18 scale)."""
        result = self._read(self.lending, keypair, "get_exchange_rate", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_borrow_index(self, keypair: Keypair, market_id: int) -> int | None:
        """Get borrow index for a market (1e18 scale)."""
        result = self._read(self.lending, keypair, "get_borrow_index", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_utilization(self, keypair: Keypair, market_id: int) -> int | None:
        """Get utilization ratio for a market (1e18 scale)."""
        result = self._read(self.lending, keypair, "get_utilization", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_borrow_rate(self, keypair: Keypair, market_id: int) -> int | None:
        """Get current borrow rate for a market (1e18 scale)."""
        result = self._read(self.lending, keypair, "get_borrow_rate", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_supply_rate(self, keypair: Keypair, market_id: int) -> int | None:
        """Get current supply rate for a market (1e18 scale)."""
        result = self._read(self.lending, keypair, "get_supply_rate", args={"market_id": market_id})
        return unwrap_option(result)

    def lending_get_underlying_balance(self, keypair: Keypair, market_id: int, user: str) -> int:
        """Get a user's underlying balance in a market."""
        result = self._read(
            self.lending, keypair, "get_underlying_balance", args={"market_id": market_id, "user": user}
        )
        return unwrap_plain(result)

    def lending_get_user_debt(self, keypair: Keypair, market_id: int, user: str) -> int:
        """Get a user's debt in a market."""
        result = self._read(
            self.lending, keypair, "get_user_debt", args={"market_id": market_id, "user": user}
        )
        return unwrap_plain(result)

    def lending_get_user_debt_details(
        self, keypair: Keypair, market_id: int, user: str
    ) -> tuple[int, int] | None:
        """Get a user's (debt, principal) in a market.

        Debt includes accrued interest; ``interest = debt - principal``.
        Returns ``None`` when the user has no position or the deployed pool
        predates principal tracking (fall back to ``lending_get_user_debt``).
        """
        result = self._read(
            self.lending,
            keypair,
            "get_user_debt_details",
            args={"market_id": market_id, "user": user},
        )
        return unwrap_option(result)

    def lending_get_last_interest_accrual_times(self, keypair: Keypair) -> tuple[int, int] | None:
        """Get the last interest-accrual timestamps (block timestamp in ms) for
        both debt markets as ``(market 0, market 1)``, or ``None`` if either
        market is missing."""
        result = self._read(self.lending, keypair, "get_last_interest_accrual_times")
        return unwrap_option(result)

    def lending_get_alpha_markets(self, keypair: Keypair) -> list:
        """Get all approved alpha markets with their params."""
        result = self._read(self.lending, keypair, "get_alpha_markets")
        return unwrap_plain(result)

    def lending_get_user_alpha_position(self, keypair: Keypair, user: str, netuid: int) -> int | None:
        """Get a user's alpha collateral position for a netuid."""
        result = self._read(
            self.lending, keypair, "get_user_alpha_position", args={"user": user, "netuid": netuid}
        )
        return unwrap_option(result)

    def lending_get_chain_timestamp(self, keypair: Keypair) -> int | None:
        """Read the chain clock (Timestamp pallet ``Now``, u64 ms) — the same
        clock the contract's ``block_timestamp()`` uses for interest accrual.
        Returns ``None`` when the read fails so callers can fall back."""
        try:
            sub = cast(Any, self.substrate)
            value = sub.query("Timestamp", "Now")
            return int(value)
        except Exception:
            return None

    def lending_get_netuid_total_collateral(self, keypair: Keypair, netuid: int) -> int | None:
        """Get total alpha collateral deposited for a netuid."""
        result = self._read(self.lending, keypair, "get_netuid_total_collateral", args={"netuid": netuid})
        return unwrap_option(result)

    def lending_is_approved_netuid(self, keypair: Keypair, netuid: int) -> bool:
        """Check if a subnet is approved for alpha collateral."""
        result = self._read(self.lending, keypair, "is_approved_netuid", args={"netuid": netuid})
        return unwrap_plain(result)

    def lending_get_active_netuids_count(self, keypair: Keypair) -> int:
        """Get the number of approved alpha netuids."""
        result = self._read(self.lending, keypair, "get_active_netuids_count")
        return unwrap_plain(result)

    def lending_get_positions(self, keypair: Keypair, user: str, page: int = 0) -> list:
        """Get paginated positions for a user."""
        result = self._read(self.lending, keypair, "get_positions", args={"user": user, "page": page})
        return unwrap_plain(result)

    def lending_get_all_positions(self, keypair: Keypair, page: int = 0) -> list:
        """Get all paginated positions across all users."""
        result = self._read(self.lending, keypair, "get_all_positions", args={"page": page})
        return unwrap_plain(result)

    def lending_get_pending_alpha_params_update(self, keypair: Keypair, netuid: int) -> dict | None:
        """Get pending alpha params update for a netuid."""
        result = self._read(self.lending, keypair, "get_pending_alpha_params_update", args={"netuid": netuid})
        return unwrap_option(result)

    def lending_get_pending_market_params_update(self, keypair: Keypair, market_id: int) -> dict | None:
        """Get pending market params update for a market."""
        result = self._read(
            self.lending, keypair, "get_pending_market_params_update", args={"market_id": market_id}
        )
        return unwrap_option(result)

    def lending_get_pending_global_params_update(self, keypair: Keypair) -> dict | None:
        """Get pending global params update."""
        result = self._read(self.lending, keypair, "get_pending_global_params_update")
        return unwrap_option(result)

    def lending_get_governance(self, keypair: Keypair) -> str:
        """Get the lending pool governance address."""
        result = self._read(self.lending, keypair, "governance")
        return unwrap_plain(result)

    def lending_get_treasury(self, keypair: Keypair) -> str:
        """Get the lending pool treasury address."""
        result = self._read(self.lending, keypair, "treasury")
        return unwrap_plain(result)

    def lending_get_platform(self, keypair: Keypair) -> str:
        """Get the lending pool platform address."""
        result = self._read(self.lending, keypair, "platform")
        return unwrap_plain(result)

    def lending_is_paused(self, keypair: Keypair) -> bool:
        """Check if the lending pool is paused."""
        result = self._read(self.lending, keypair, "paused")
        return unwrap_plain(result)

    def lending_get_oracle_address(self, keypair: Keypair) -> str:
        """Get the lending pool oracle address."""
        result = self._read(self.lending, keypair, "get_oracle_address")
        return unwrap_plain(result)

    def lending_get_tusdt_address(self, keypair: Keypair) -> str:
        """Get the lending pool TUSDT address."""
        result = self._read(self.lending, keypair, "get_tusdt_address")
        return unwrap_plain(result)

    def lending_get_ltoken_address(self, keypair: Keypair, market_id: int) -> str | None:
        """Get an lToken child contract address."""
        result = self._read(self.lending, keypair, "get_ltoken_address", args={"market": market_id})
        return unwrap_option(result)

    def lending_get_pool_hotkey(self, keypair: Keypair) -> str:
        """Get the lending pool hotkey address."""
        result = self._read(self.lending, keypair, "get_pool_hotkey")
        return unwrap_plain(result)

    def lending_get_global_params(self, keypair: Keypair) -> dict:
        """Get current global pool parameters."""
        result = self._read(self.lending, keypair, "get_global_params")
        return unwrap_plain(result)

    def lending_get_tao_staked(self, keypair: Keypair) -> int:
        """Get the booked TAO currently staked on the root subnet (raw rao)."""
        result = self._read(self.lending, keypair, "get_tao_staked")
        return unwrap_result(result)

    def lending_get_root_stake_config(self, keypair: Keypair) -> dict:
        """Get the current idle-TAO root-subnet staking configuration."""
        result = self._read(self.lending, keypair, "get_root_stake_config")
        return unwrap_result(result)

    def lending_get_market_params(self, keypair: Keypair, market_id: int) -> dict | None:
        """Get interest-rate parameters for a market (0 = TAO, 1 = TUSDT).

        Returns None when the market has no configured params.
        """
        result = self._read(
            self.lending,
            keypair,
            "get_market_params",
            args={"market_id": market_id},
        )
        return unwrap_option(result)

    def lending_get_alpha_params(self, keypair: Keypair, netuid: int) -> dict | None:
        """Get alpha market parameters for a subnet.

        Returns None when the netuid has no configured params.
        """
        result = self._read(
            self.lending,
            keypair,
            "get_alpha_params",
            args={"netuid": netuid},
        )
        return unwrap_option(result)

    def lending_get_maintainer(self, keypair: Keypair) -> str:
        """Get the pool maintainer address."""
        result = self._read(self.lending, keypair, "maintainer")
        return unwrap_plain(result)

    def lending_update_maintainer(
        self, keypair: Keypair, new_maintainer: str
    ) -> dict[str, Any] | DryRunResult:
        """Update the pool maintainer (governance-gated)."""
        return self._exec(
            self.lending,
            keypair,
            "update_maintainer",
            args={"new_maintainer": new_maintainer},
        )
