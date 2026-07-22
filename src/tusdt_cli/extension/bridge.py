"""Bridge server that connects browser extensions to the Python CLI.

Starts an async HTTP + WebSocket server on a local port, serves a static
bridge HTML page, and relays messages between the browser extension and
the Python client.

Two WebSocket roles:
- ``"bridge"`` — the browser tab that talks to ``window.injectedWeb3``.
- ``"client"`` — the Python CLI process.

Adapted from btcli's ``bittensor/extension/bridge.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import http.server
import json
import uuid
from typing import Any

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 39295

_BRIDGE_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>tusdt-cli Bridge</title></head>
<body>
<h1>tusdt-cli Extension Bridge</h1>
<p id="status">Connecting...</p>
<pre id="log"></pre>
<script>
const WS_URL = `ws://${location.host}/ws`;
let ws;
let accounts = [];

function log(msg) {
    const el = document.getElementById('log');
    el.textContent += msg + '\\n';
    console.log(msg);
}

async function connect() {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
        log('WebSocket connected');
        ws.send(JSON.stringify({type: 'auth', role: 'bridge', token: BRIDGE_TOKEN}));
    };
    ws.onmessage = async (e) => {
        const msg = JSON.parse(e.data);
        log('RECV: ' + JSON.stringify(msg));
        if (msg.method === 'accounts.list') {
            await listAccounts(msg.id);
        } else if (msg.method === 'extrinsic.sign') {
            await signExtrinsic(msg.id, msg.params.payload);
        } else if (msg.method === 'bytes.sign') {
            await signBytes(msg.id, msg.params.address, msg.params.data);
        }
    };
    ws.onclose = () => {
        log('WebSocket disconnected');
        document.getElementById('status').textContent = 'Disconnected';
    };
}
function respond(id, result) {
    ws.send(JSON.stringify({id, result}));
}
function error(id, message) {
    ws.send(JSON.stringify({id, error: {message}}));
}
async function listAccounts(id) {
    try {
        if (!window.injectedWeb3) {
            return error(id, 'No injectedWeb3 found. Install Polkadot.js or Talisman extension.');
        }
        const ext = window.injectedWeb3['polkadot-js'];
        if (!ext) {
            return error(id, 'Polkadot.js extension not found in injectedWeb3.');
        }
        const injected = await ext.enable('tusdt-cli');
        const all = await injected.accounts.get();
        accounts = all.map(a => ({address: a.address, name: a.name || '', source: 'polkadot-js'}));
        respond(id, {accounts});
        document.getElementById('status').textContent =
            `Connected: ${accounts.length} account(s)`;
    } catch (e) {
        error(id, e.message || String(e));
    }
}
async function signExtrinsic(id, payload) {
    try {
        const addr = payload.address;
        const ext = window.injectedWeb3['polkadot-js'];
        if (!ext) return error(id, 'Extension not found');
        const injected = await ext.enable('tusdt-cli');
        const result = await injected.signer.signRaw({
            address: addr,
            data: payload.data || '',
            type: 'bytes'
        });
        respond(id, {signature: result.signature});
    } catch (e) {
        error(id, e.message || String(e));
    }
}
async function signBytes(id, address, data) {
    try {
        const ext = window.injectedWeb3['polkadot-js'];
        if (!ext) return error(id, 'Extension not found');
        const injected = await ext.enable('tusdt-cli');
        const result = await injected.signer.signRaw({
            address: address,
            data: data,
            type: 'bytes'
        });
        respond(id, {signature: result.signature});
    } catch (e) {
        error(id, e.message || String(e));
    }
}
connect();
</script>
</body></html>"""


class BridgeServer:
    """Async bridge server. Start with ``await server.start()``."""

    def __init__(self, host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT):
        self._host = host
        self._port = port
        self._sessions: dict[str, Any] = {}
        self._authenticated: set[str] = set()
        self._pending: dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """Start the bridge server (blocking).

        Generates and persists an auth token that both the CLI client
        and the bridge HTML page must present to connect.
        """
        from .tokens import write_bridge_token

        self._auth_token = write_bridge_token()
        await asyncio.gather(
            self._run_ws(),
            self._run_http(),
        )

    async def _run_ws(self) -> None:
        from websockets import serve

        expected_origin = f"http://{self._host}:{self._port + 1}"

        async def check_origin(connection, request):
            origin = request.headers.get("Origin", "")
            if origin and origin != expected_origin:
                return connection.terminate(403, "Forbidden")
            return None

        async def handler(ws):
            session_id = uuid.uuid4().hex[:8]
            self._sessions[session_id] = ws
            try:
                async for raw in ws:
                    await self._handle_message(session_id, raw)
            finally:
                self._sessions.pop(session_id, None)
                self._authenticated.discard(session_id)

        async with serve(handler, self._host, self._port, process_request=check_origin):
            await asyncio.Future()  # run forever

    async def _run_http(self) -> None:
        # Serve the bridge HTML on port+1 (the main port is for WebSocket).
        # The auth token is embedded as a JS variable so the bridge page can
        # authenticate its WebSocket connection.
        http_port = self._port + 1
        bridge = self  # capture for the inner class

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                html = _BRIDGE_HTML.replace(
                    "const WS_URL =",
                    f"const BRIDGE_TOKEN = {json.dumps(bridge._auth_token)};\n        const WS_URL =",
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; connect-src ws://127.0.0.1:*; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
                )
                self.end_headers()
                self.wfile.write(html)

            def log_message(self, format, *args):
                pass

        server = http.server.HTTPServer((self._host, http_port), Handler)
        await asyncio.to_thread(server.serve_forever)

    async def _handle_message(self, session_id: str, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw if isinstance(raw, str) else raw.decode())
            msg_type = msg.get("type", msg.get("method", ""))

            if msg_type == "auth":
                # Verify the auth token matches — only the CLI client (which
                # reads the token file) and the bridge page (which embeds it)
                # should possess this token.
                provided = msg.get("token", "")
                if provided != self._auth_token:
                    ws = self._sessions.get(session_id)
                    if ws:
                        await ws.send(
                            json.dumps(
                                {
                                    "id": msg.get("id", ""),
                                    "error": {"message": "unauthorized: invalid auth token"},
                                }
                            )
                        )
                        await ws.close(4001, "unauthorized")
                    self._sessions.pop(session_id, None)
                    return
                self._authenticated.add(session_id)
                ws = self._sessions.get(session_id)
                if ws:
                    await ws.send(json.dumps({"id": msg.get("id", ""), "result": {"status": "ok"}}))

            elif "id" in msg:
                # Require authentication before relaying.
                if session_id not in self._authenticated:
                    ws = self._sessions.get(session_id)
                    if ws:
                        await ws.send(
                            json.dumps(
                                {
                                    "id": msg.get("id", ""),
                                    "error": {"message": "unauthorized: not authenticated"},
                                }
                            )
                        )
                    return

                # It's a JSON-RPC request — relay to the bridge role.
                bridged = False
                for sid, ws in list(self._sessions.items()):
                    if sid == session_id:
                        continue
                    try:
                        await ws.send(json.dumps(msg))
                        # Wait for the response via the pending future.
                        future: asyncio.Future = asyncio.get_event_loop().create_future()
                        self._pending[msg["id"]] = future
                        result = await asyncio.wait_for(future, timeout=60.0)
                        client_ws = self._sessions.get(session_id)
                        if client_ws:
                            await client_ws.send(json.dumps({"id": msg["id"], "result": result}))
                        bridged = True
                        break
                    except asyncio.TimeoutError:
                        pass
                if not bridged:
                    ws = self._sessions.get(session_id)
                    if ws:
                        await ws.send(
                            json.dumps(
                                {"id": msg.get("id", ""), "error": {"message": "no bridge session available"}}
                            )
                        )

            elif msg_type == "result" or "result" in msg:
                # Require authentication before processing responses.
                if session_id not in self._authenticated:
                    return

                # Response from bridge to a pending request.
                rid = msg.get("id", "")
                future = self._pending.pop(rid, None)
                if future and not future.done():
                    future.set_result(msg.get("result", msg))

        except Exception:
            pass


def run_bridge() -> None:
    """Entry point for the bridge daemon."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_BRIDGE_PORT)
    args = parser.parse_args()

    server = BridgeServer(port=args.port)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(server.start())


if __name__ == "__main__":
    run_bridge()
