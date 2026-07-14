"""Substrate/ink! contract client for the TUSDT system.

Wraps ``SubstrateInterface`` and ``ContractInstance`` to provide typed
methods for the Vault, Token (ERC-20), Auction, Oracle, Governance, and
Treasury contracts.
"""

import logging
from time import sleep
from typing import Any

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
        self._vault: ContractInstance | None = None
        self._token: ContractInstance | None = None
        self._auction: ContractInstance | None = None
        self._oracle: ContractInstance | None = None
        self._governance: ContractInstance | None = None
        self._treasury: ContractInstance | None = None
        self._election: ContractInstance | None = None

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
    ) -> dict[str, Any]:
        """Dry-run for gas estimation, then submit the extrinsic.

        Shows a step-by-step progress spinner:
          1. Estimating gas...
          2. Submitting transaction...
          3. Finalized

        Returns a dict with ``extrinsic_hash`` and ``block_hash`` on success.
        Raises ``ContractError`` on failure.
        """
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

    # ==================================================================
    # VAULT OPERATIONS
    # ==================================================================

    def create_vault(self, keypair: Keypair, amount: int) -> dict[str, Any]:
        """Create a new vault, depositing *amount* native tokens as collateral."""
        return self._exec(self.vault, keypair, "create_vault", value=amount)

    def add_collateral(self, keypair: Keypair, vault_id: int, amount: int) -> dict[str, Any]:
        """Add collateral to an existing vault."""
        return self._exec(self.vault, keypair, "add_collateral", args={"vault_id": vault_id}, value=amount)

    def borrow(self, keypair: Keypair, vault_id: int, amount: int) -> dict[str, Any]:
        """Borrow TUSDT tokens against a vault's collateral."""
        return self._exec(self.vault, keypair, "borrow_token", args={"vault_id": vault_id, "amount": amount})

    def repay(self, keypair: Keypair, vault_id: int, amount: int) -> dict[str, Any]:
        """Repay borrowed TUSDT tokens."""
        return self._exec(self.vault, keypair, "repay_token", args={"vault_id": vault_id, "amount": amount})

    def release_collateral(self, keypair: Keypair, vault_id: int, amount: int) -> dict[str, Any]:
        """Release collateral from a vault."""
        return self._exec(
            self.vault, keypair, "release_collateral", args={"vault_id": vault_id, "amount": amount}
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

    def get_contract_params(self, keypair: Keypair) -> dict:
        """Return the vault contract parameters."""
        result = self._read(self.vault, keypair, "get_contract_params")
        raw = unwrap_plain(result)
        return raw if isinstance(raw, dict) else raw

    def accrue_interest(self, keypair: Keypair, owner: str, vault_id: int) -> dict[str, Any]:
        """Accrue interest on a vault."""
        return self._exec(self.vault, keypair, "accrue_interest", args={"owner": owner, "vault_id": vault_id})

    def trigger_liquidation(self, keypair: Keypair, owner: str, vault_id: int) -> dict[str, Any]:
        """Trigger a liquidation auction for an undercollateralized vault."""
        return self._exec(
            self.vault, keypair, "trigger_liquidation_auction", args={"owner": owner, "vault_id": vault_id}
        )

    def settle_liquidation(self, keypair: Keypair, owner: str, vault_id: int) -> dict[str, Any]:
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

    def get_platform(self, keypair: Keypair) -> str:
        """Return the current platform account address."""
        result = self._read(self.vault, keypair, "platform")
        return unwrap_plain(result)

    def is_paused(self, keypair: Keypair) -> bool:
        """Return whether the vault contract is paused."""
        result = self._read(self.vault, keypair, "paused")
        return unwrap_plain(result)

    def get_pending_params_update(self, keypair: Keypair) -> dict | None:
        """Return the pending contract parameter update, if any."""
        result = self._read(self.vault, keypair, "get_pending_contract_params_update")
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    def update_governance(self, keypair: Keypair, new_governance: str) -> dict[str, Any]:
        """Transfer governance to a new account."""
        return self._exec(self.vault, keypair, "update_governance", args={"new_governance": new_governance})

    def update_platform(self, keypair: Keypair, new_platform: str) -> dict[str, Any]:
        """Update the platform account."""
        return self._exec(self.vault, keypair, "update_platform", args={"new_platform": new_platform})

    def pause_contract(self, keypair: Keypair) -> dict[str, Any]:
        """Pause the vault contract."""
        return self._exec(self.vault, keypair, "pause")

    def unpause_contract(self, keypair: Keypair) -> dict[str, Any]:
        """Unpause the vault contract."""
        return self._exec(self.vault, keypair, "unpause")

    def set_contract_params(
        self,
        keypair: Keypair,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Schedule a contract parameter update with timelock.

        Reads current on-chain params, merges with user-supplied changes,
        and sends the complete 11-field VaultContractParamsConfig struct.
        """
        current = unwrap_plain(self._read(self.vault, keypair, "get_contract_params"))
        if not isinstance(current, dict):
            raise ContractError(f"Expected dict from get_contract_params, got {type(current).__name__}")
        merged = dict(current)
        merged.update(params)
        return self._exec(self.vault, keypair, "set_contract_params", args={"params": merged})

    def execute_params_update(self, keypair: Keypair) -> dict[str, Any]:
        """Execute the pending contract parameter update after timelock."""
        return self._exec(self.vault, keypair, "execute_contract_params_update")

    def cancel_params_update(self, keypair: Keypair) -> dict[str, Any]:
        """Cancel the pending contract parameter update."""
        return self._exec(self.vault, keypair, "cancel_contract_params_update")

    def claim_surplus_tusdt(self, keypair: Keypair, amount: int) -> dict[str, Any]:
        """Claim surplus TUSDT tokens held by the vault contract."""
        return self._exec(self.vault, keypair, "claim_surplus_tusdt", args={"amount": amount})

    def vault_get_treasury(self, keypair: Keypair) -> str:
        """Return the treasury address from the vault contract."""
        result = self._read(self.vault, keypair, "treasury")
        return unwrap_plain(result)

    def vault_update_treasury(self, keypair: Keypair, new_treasury: str) -> dict[str, Any]:
        """Update the treasury address in the vault contract (governance only)."""
        return self._exec(self.vault, keypair, "update_treasury", args={"new_treasury": new_treasury})

    def vault_emergency_drain(self, keypair: Keypair, recipient: str) -> dict[str, Any]:
        """Emergency drain native balance from the vault (TESTNET ONLY, governance)."""
        return self._exec(self.vault, keypair, "emergency_drain", args={"recipient": recipient})

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

    def set_council(self, keypair: Keypair, members: list) -> dict[str, Any]:
        """Set the council member list (maintainer only)."""
        return self._exec(self.governance, keypair, "set_council", args={"members": members})

    def gov_vault_set_contract_params(self, keypair: Keypair, params: dict) -> dict[str, Any]:
        """Schedule a vault contract parameter update via governance.

        Reads current on-chain params from the vault, merges with user-supplied
        changes, and sends the complete 11-field struct via governance forwarder.
        """
        current = unwrap_plain(self._read(self.vault, keypair, "get_contract_params"))
        if not isinstance(current, dict):
            raise ContractError(f"Expected dict from get_contract_params, got {type(current).__name__}")
        merged = dict(current)
        merged.update(params)
        return self._exec(self.governance, keypair, "vault_set_contract_params", args={"params": merged})

    def gov_vault_cancel_update(self, keypair: Keypair) -> dict[str, Any]:
        """Cancel a pending vault contract parameter update via governance."""
        return self._exec(self.governance, keypair, "vault_cancel_contract_params_update")

    def gov_vault_update_treasury(self, keypair: Keypair, new_treasury: str) -> dict[str, Any]:
        """Update the vault treasury address via governance."""
        return self._exec(
            self.governance, keypair, "vault_update_treasury", args={"new_treasury": new_treasury}
        )

    def gov_vault_update_platform(self, keypair: Keypair, new_platform: str) -> dict[str, Any]:
        """Update the vault platform address via governance."""
        return self._exec(
            self.governance, keypair, "vault_update_platform", args={"new_platform": new_platform}
        )

    def gov_vault_unpause(self, keypair: Keypair) -> dict[str, Any]:
        """Unpause the vault contract via governance."""
        return self._exec(self.governance, keypair, "vault_unpause")

    def gov_vault_pause(self, keypair: Keypair) -> dict[str, Any]:
        """Pause the vault contract via governance."""
        return self._exec(self.governance, keypair, "vault_pause")

    def gov_oracle_set_validator(self, keypair: Keypair, validator: str | None) -> dict[str, Any]:
        """Set the oracle validator via governance (pass None to clear)."""
        return self._exec(self.governance, keypair, "oracle_set_validator", args={"validator": validator})

    def gov_oracle_set_max_price_deviation(
        self, keypair: Keypair, max_price_deviation: int
    ) -> dict[str, Any]:
        """Set the oracle max price deviation via governance."""
        return self._exec(
            self.governance,
            keypair,
            "oracle_set_max_price_deviation",
            args={"max_price_deviation": max_price_deviation},
        )

    def gov_oracle_commit_round(self, keypair: Keypair, price: int) -> dict[str, Any]:
        """Commit the oracle round with an explicit price via governance."""
        return self._exec(self.governance, keypair, "oracle_commit_round", args={"price": price})

    def gov_oracle_set_netuid(self, keypair: Keypair, netuid: int) -> dict[str, Any]:
        """Set the oracle's governing subnet netuid via governance."""
        return self._exec(self.governance, keypair, "oracle_set_netuid", args={"netuid": netuid})

    def gov_oracle_set_min_submitter_stake(self, keypair: Keypair, min_stake: int) -> dict[str, Any]:
        """Set the oracle's minimum submitter stake via governance."""
        return self._exec(
            self.governance, keypair, "oracle_set_min_submitter_stake", args={"min_stake": min_stake}
        )

    def gov_auction_set_admin(self, keypair: Keypair, admin: str | None) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def submit_proposal(self, keypair: Keypair, cid: str, kind: dict) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def finalize_proposal(self, keypair: Keypair, proposal_id: int) -> dict[str, Any]:
        """Finalize a governance proposal."""
        return self._exec(self.governance, keypair, "finalize", args={"proposal_id": proposal_id})

    def execute_proposal(self, keypair: Keypair, proposal_id: int) -> dict[str, Any]:
        """Execute a finalized governance proposal."""
        return self._exec(self.governance, keypair, "execute", args={"proposal_id": proposal_id})

    def submit_snapshot(
        self,
        keypair: Keypair,
        root: list,
        circulating_supply: int,
        snapshot_block: int,
    ) -> dict[str, Any]:
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

    def approve(self, keypair: Keypair, spender: str, amount: int) -> dict[str, Any]:
        """Approve *spender* to spend *amount* TUSDT tokens."""
        return self._exec(self.token, keypair, "approve", args={"spender": spender, "value": amount})

    def transfer(self, keypair: Keypair, to: str, amount: int) -> dict[str, Any]:
        """Transfer *amount* TUSDT tokens to *to*."""
        return self._exec(self.token, keypair, "transfer", args={"to": to, "value": amount})

    def token_controller(self, keypair: Keypair) -> str:
        """Return the controller address of the TUSDT token contract."""
        result = self._read(self.token, keypair, "controller")
        return unwrap_plain(result)

    def token_mint(self, keypair: Keypair, to: str, amount: int) -> dict[str, Any]:
        """Mint *amount* TUSDT tokens to *to* (controller only)."""
        return self._exec(self.token, keypair, "mint", args={"to": to, "value": amount})

    def token_burn(self, keypair: Keypair, from_addr: str, amount: int) -> dict[str, Any]:
        """Burn *amount* TUSDT tokens from *from_addr* (controller only)."""
        return self._exec(self.token, keypair, "burn", args={"from": from_addr, "value": amount})

    def token_increase_allowance(self, keypair: Keypair, spender: str, delta: int) -> dict[str, Any]:
        """Increase *spender*'s allowance by *delta* TUSDT tokens."""
        return self._exec(
            self.token, keypair, "increase_allowance", args={"spender": spender, "delta_value": delta}
        )

    def token_decrease_allowance(self, keypair: Keypair, spender: str, delta: int) -> dict[str, Any]:
        """Decrease *spender*'s allowance by *delta* TUSDT tokens."""
        return self._exec(
            self.token, keypair, "decrease_allowance", args={"spender": spender, "delta_value": delta}
        )

    def token_transfer_from(self, keypair: Keypair, from_addr: str, to: str, amount: int) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def finalize_auction(self, keypair: Keypair, auction_id: int) -> dict[str, Any]:
        """Finalize an auction after its end time."""
        return self._exec(self.auction, keypair, "finalize_auction", args={"auction_id": auction_id})

    def withdraw_refund(self, keypair: Keypair, auction_id: int, bid_id: int) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def auction_set_admin(self, keypair: Keypair, admin: str | None) -> dict[str, Any]:
        """Set or clear the auction admin (governance only). Pass None to clear."""
        return self._exec(self.auction, keypair, "set_admin", args={"admin": admin})

    def auction_update_governance(self, keypair: Keypair, new_governance: str) -> dict[str, Any]:
        """Transfer auction governance to a new account (controller only)."""
        return self._exec(self.auction, keypair, "update_governance", args={"new_governance": new_governance})

    def auction_transfer_winning_bid(
        self,
        keypair: Keypair,
        auction_id: int,
        recipient: str,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        """Submit a price to the oracle. The caller must be a registered subnet neuron."""
        provider_bytes = provider.encode() if provider else None
        args: dict[str, Any] = {
            "price": price,
            "metadata": {"hot_key": hot_key, "provider": provider_bytes},
        }
        return self._exec(self.oracle, keypair, "submit_price", args=args)

    def commit_round(self, keypair: Keypair, override_price: int | None = None) -> dict[str, Any]:
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

    def commit_round_governance(self, keypair: Keypair, price: int) -> dict[str, Any]:
        """Governance commits the current oracle round with an explicit price."""
        return self._exec(self.oracle, keypair, "commit_round_governance", args={"price": price})

    def oracle_get_netuid(self, keypair: Keypair) -> int:
        """Return the oracle's governing subnet netuid."""
        result = self._read(self.oracle, keypair, "get_netuid")
        return unwrap_plain(result)

    def oracle_set_netuid(self, keypair: Keypair, netuid: int) -> dict[str, Any]:
        """Set the oracle's governing subnet netuid (governance only)."""
        return self._exec(self.oracle, keypair, "set_netuid", args={"netuid": netuid})

    def oracle_get_min_submitter_stake(self, keypair: Keypair) -> int:
        """Return the oracle's minimum required submitter stake."""
        result = self._read(self.oracle, keypair, "min_submitter_stake")
        return unwrap_plain(result)

    def oracle_set_min_submitter_stake(self, keypair: Keypair, min_stake: int) -> dict[str, Any]:
        """Set the oracle's minimum submitter stake (governance only)."""
        return self._exec(self.oracle, keypair, "set_min_submitter_stake", args={"min_stake": min_stake})

    def set_validator(self, keypair: Keypair, validator: str | None) -> dict[str, Any]:
        """Set the oracle validator account (governance only). Pass None to clear."""
        return self._exec(self.oracle, keypair, "set_validator", args={"validator": validator})

    def set_max_price_deviation(self, keypair: Keypair, max_price_deviation: int) -> dict[str, Any]:
        """Set the maximum allowed price deviation between rounds (governance only)."""
        return self._exec(
            self.oracle,
            keypair,
            "set_max_price_deviation",
            args={"max_price_deviation": max_price_deviation},
        )

    def oracle_update_governance(self, keypair: Keypair, new_governance: str) -> dict[str, Any]:
        """Transfer oracle governance to a new account (controller only)."""
        return self._exec(self.oracle, keypair, "update_governance", args={"new_governance": new_governance})

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

    def treasury_set_governance(self, keypair: Keypair, new_governance: str) -> dict[str, Any]:
        """Set a new governance address for the treasury (governance only)."""
        return self._exec(self.treasury, keypair, "set_governance", args={"new_governance": new_governance})

    def treasury_distribute(self, keypair: Keypair) -> dict[str, Any]:
        """Distribute pending funds to their respective fund balances."""
        return self._exec(self.treasury, keypair, "distribute")

    def treasury_release(
        self,
        keypair: Keypair,
        fund: dict,
        token_kind: dict,
        amount: int,
        recipient: str,
    ) -> dict[str, Any]:
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

    def schedule_election(self, keypair: Keypair) -> dict[str, Any]:
        """Schedule a new election cycle (permissionless)."""
        return self._exec(self.election, keypair, "schedule_election")

    def register_candidate(self, keypair: Keypair, netuid: int, hotkey: str) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def finalize_election(self, keypair: Keypair) -> dict[str, Any]:
        """Finalize the current election cycle (permissionless)."""
        return self._exec(self.election, keypair, "finalize")

    def activate_election(self, keypair: Keypair) -> dict[str, Any]:
        """Activate the elected maintainer (permissionless)."""
        return self._exec(self.election, keypair, "activate")

    def end_transition(self, keypair: Keypair) -> dict[str, Any]:
        """End the active subnet transition (permissionless)."""
        return self._exec(self.election, keypair, "end_transition")

    def trigger_emergency_election(self, keypair: Keypair) -> dict[str, Any]:
        """Trigger an emergency election (incumbent only)."""
        return self._exec(self.election, keypair, "trigger_emergency_election")

    def cancel_cycle(self, keypair: Keypair) -> dict[str, Any]:
        """Cancel the current election cycle (incumbent only)."""
        return self._exec(self.election, keypair, "cancel_cycle")
