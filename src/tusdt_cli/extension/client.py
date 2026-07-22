"""WebSocket bridge client for talking to the extension bridge server.

The Python CLI connects as a ``"client"`` role over WebSocket and sends
JSON-RPC requests. The bridge server relays them to the browser extension.

Adapted from btcli's ``bittensor/extension/client.py``.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from .errors import BridgeError
from .tokens import read_bridge_token

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 39295


def _bridge_url(host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT) -> str:
    return f"ws://{host}:{port}/ws"


class BridgeClient:
    """WebSocket RPC client to the running bridge server.

    Methods mirror the bridge protocol:
    - ``list_accounts()`` — list extension accounts
    - ``sign_extrinsic_payload(payload)`` — sign via Polkadot-JS SignerPayloadJSON
    - ``sign_bytes(address, data_hex)`` — sign raw bytes
    - ``report_transaction_result(success)`` — notify bridge of tx outcome
    - ``ping()`` — health check
    """

    def __init__(self, host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT):
        self._url = _bridge_url(host, port)
        self._ws: Any = None
        self._token = read_bridge_token()

    async def connect(self) -> None:
        """Connect to the bridge server and authenticate."""
        try:
            self._ws = await asyncio.wait_for(websockets.connect(self._url), timeout=5.0)
        except asyncio.TimeoutError:
            raise BridgeError(f"bridge at {self._url} is not responding") from None
        except OSError as e:
            raise BridgeError(f"cannot reach bridge at {self._url}: {e}") from e

        # Authenticate as client.
        await self._ws.send(
            json.dumps(
                {
                    "type": "auth",
                    "role": "client",
                    "token": self._token or "",
                }
            )
        )
        reply = await self._recv()
        if reply.get("status") != "ok":
            raise BridgeError(f"bridge auth failed: {reply.get('error', 'unknown')}")

    async def _call(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        request_id = uuid.uuid4().hex[:8]
        msg = {"id": request_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(msg))
        reply = await self._recv()
        if reply.get("error"):
            raise BridgeError(reply["error"].get("message", "unknown bridge error"))
        return reply.get("result", {})

    async def _recv(self) -> dict:
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=30.0)
            return json.loads(raw)
        except asyncio.TimeoutError:
            raise BridgeError("bridge request timed out") from None
        except ConnectionClosed as e:
            raise BridgeError(f"bridge connection closed: {e}") from e

    async def list_accounts(self) -> list[dict]:
        """Return a list of accounts from the connected extension."""
        result = await self._call("accounts.list")
        return result.get("accounts", [])

    async def sign_extrinsic_payload(self, payload: dict) -> dict:
        """Sign a Polkadot-JS SignerPayloadJSON and return ``{"signature": "0x..."}``."""
        return await self._call("extrinsic.sign", {"payload": payload})

    async def sign_bytes(self, address: str, data_hex: str) -> str:
        """Sign raw bytes and return the signature hex string."""
        result = await self._call("bytes.sign", {"address": address, "data": data_hex})
        return result.get("signature", "")

    async def report_transaction_result(self, success: bool) -> None:
        """Notify the bridge page of transaction success/failure."""
        await self._call("transaction.result", {"success": success})

    async def ping(self) -> bool:
        """Health check — returns True if the bridge is alive."""
        try:
            result = await self._call("bridge.status")
            return result.get("status") == "ok"
        except BridgeError:
            return False

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
