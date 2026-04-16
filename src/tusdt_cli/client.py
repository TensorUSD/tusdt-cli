"""Substrate/ink! contract client for the TUSDT system.

Wraps ``SubstrateInterface`` and ``ContractInstance`` to provide typed
methods for the Vault, Token (ERC-20), Auction, and Oracle contracts.
"""

from typing import Any, Optional

from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.contracts import ContractInstance, ContractMetadata
from substrateinterface.exceptions import ContractReadFailedException

from tusdt_cli.utils import (
    ContractError,
    console,
    unwrap_option,
    unwrap_plain,
    unwrap_query,
    unwrap_result,
)


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


class TUSDTClient:
    """High-level client for the four TUSDT contracts."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._substrate: Optional[SubstrateInterface] = None
        self._vault: Optional[ContractInstance] = None
        self._token: Optional[ContractInstance] = None
        self._auction: Optional[ContractInstance] = None
        self._oracle: Optional[ContractInstance] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def substrate(self) -> SubstrateInterface:
        if self._substrate is None:
            rpc = self.config.get("rpc")
            if not rpc:
                raise ValueError("RPC endpoint not configured. Run: tusdt config set --rpc <url>")
            self._substrate = SubstrateInterface(
                url=rpc,
                use_remote_preset=True,
                type_registry={"types": {"Balance": "u64"}},
            )
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
        return self._exec(self.vault, keypair, "release_collateral", args={"vault_id": vault_id, "amount": amount})

    def get_vault(self, keypair: Keypair, owner: str, vault_id: int) -> Optional[dict]:
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
        result = self._read(self.vault, keypair, "get_max_borrow", args={"owner": owner, "vault_id": vault_id})
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

    def get_liquidation_auction_id(self, keypair: Keypair, owner: str, vault_id: int) -> Optional[int]:
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

    def get_auction(self, keypair: Keypair, auction_id: int) -> Optional[dict]:
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
        hot_key: Optional[str] = None,
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

    def get_my_bid(self, keypair: Keypair, auction_id: int, bidder: str) -> Optional[dict]:
        """Get the caller's bid in an auction."""
        result = self._read(self.auction, keypair, "get_auction_bid", args={"auction_id": auction_id, "bidder": bidder})
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

    def get_active_vault_auction(self, keypair: Keypair, vault_owner: str, vault_id: int) -> Optional[int]:
        """Return the active auction ID for a specific vault, or ``None``."""
        result = self._read(
            self.auction, keypair, "get_active_vault_auction",
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

    def get_bid(self, keypair: Keypair, auction_id: int, bid_id: int) -> Optional[dict]:
        """Get a specific bid by auction ID and bid ID."""
        result = self._read(self.auction, keypair, "get_bid", args={"auction_id": auction_id, "bid_id": bid_id})
        raw = unwrap_option(result)
        if raw is None:
            return None
        return raw if isinstance(raw, dict) else raw

    # ==================================================================
    # ORACLE OPERATIONS
    # ==================================================================

    def get_latest_price(self, keypair: Keypair) -> Optional[dict]:
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

    def submit_price(self, keypair: Keypair, price: int, hot_key: Optional[str] = None) -> dict[str, Any]:
        """Submit a price to the oracle as a reporter."""
        args: dict[str, Any] = {"price": price}
        if hot_key:
            args["metadata"] = {"hot_key": hot_key}
        else:
            args["metadata"] = None
        return self._exec(self.oracle, keypair, "submit_price", args=args)

    def commit_round(self, keypair: Keypair, override_price: Optional[int] = None) -> dict[str, Any]:
        """Commit the current oracle round. Optionally override the median price."""
        args: dict[str, Any] = {"override_price": override_price}
        return self._exec(self.oracle, keypair, "commit_round", args=args)

    def get_round_price(self, keypair: Keypair, round_id: int) -> Optional[dict]:
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

    def is_reporter(self, keypair: Keypair, account: str) -> bool:
        """Check if an account is a registered oracle reporter."""
        result = self._read(self.oracle, keypair, "is_reporter", args={"account": account})
        return unwrap_plain(result)
