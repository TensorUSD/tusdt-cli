"""Typed errors for the TUSDT CLI.

Every error carries a machine-readable :class:`ErrorCode` and a short remediation
hint so callers can branch on the failure and know what to try next, instead of
parsing a human sentence.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Machine-readable error classification."""

    CONNECTION_FAILED = "connection_failed"
    CONTRACT_READ_FAILED = "contract_read_failed"
    CONTRACT_EXEC_FAILED = "contract_exec_failed"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    NOT_CONFIGURED = "not_configured"
    WALLET_NOT_FOUND = "wallet_not_found"
    WALLET_DECRYPT_FAILED = "wallet_decrypt_failed"
    INVALID_ARGUMENT = "invalid_argument"
    NETWORK_ERROR = "network_error"
    LEDGER_ERROR = "ledger_error"
    UNKNOWN = "unknown"


class TUSDTError(Exception):
    """Base exception for all TUSDT CLI errors.

    Carries a :class:`ErrorCode` so callers can branch on the failure type
    rather than parsing the message string.
    """

    def __init__(self, message: str, code: ErrorCode = ErrorCode.UNKNOWN) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# Rustc help conventions: lowercase, no trailing punctuation, states the fix.
# Commands are backticked so the CLI renders them in the command style.
REMEDIATION: dict[ErrorCode, str] = {
    ErrorCode.CONNECTION_FAILED: (
        "check the RPC endpoint is reachable from your network; "
        "run `tusdt config set --rpc <url>` to change it"
    ),
    ErrorCode.CONTRACT_READ_FAILED: (
        "the contract query failed; verify the contract address and ABI metadata "
        "are correct with `tusdt config show`"
    ),
    ErrorCode.CONTRACT_EXEC_FAILED: (
        "the transaction failed on-chain; check the error details above and verify "
        "your account has sufficient balance for gas"
    ),
    ErrorCode.INSUFFICIENT_BALANCE: (
        "your account does not have enough balance to cover the amount plus "
        "transaction fees; check with `tusdt token balance`"
    ),
    ErrorCode.NOT_CONFIGURED: (
        "a required contract address or RPC endpoint is missing; "
        "run `tusdt config set --<name> <address>` to set it, "
        "or `tusdt config set --network finney` to use defaults"
    ),
    ErrorCode.WALLET_NOT_FOUND: (
        "no bittensor wallet found with that name; check available wallets with `tusdt wallet list`"
    ),
    ErrorCode.WALLET_DECRYPT_FAILED: (
        "the coldkey password is incorrect or the keyfile is corrupt; check the wallet name and try again"
    ),
    ErrorCode.INVALID_ARGUMENT: (
        "check the argument values and try again; run `tusdt <command> --help` for usage"
    ),
    ErrorCode.NETWORK_ERROR: (
        "a network error occurred while talking to the chain; "
        "the request will be retried automatically if transient, "
        "otherwise check your connection and RPC endpoint"
    ),
    ErrorCode.LEDGER_ERROR: (
        "check the device is connected, unlocked, and the Polkadot app is open; "
        "install hid support with `pip install tusdt-cli[ledger]` if missing"
    ),
    ErrorCode.UNKNOWN: ("an unexpected error occurred; inspect the message above for details"),
}
