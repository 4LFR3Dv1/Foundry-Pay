"""Minimal persistent Solana JSON-RPC upstream for process-boundary tests."""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class UpstreamStore:
    def __init__(self, path: Path, expected_signature: str):
        self.path = path
        self.expected_signature = expected_signature
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accepted_transactions (
                    signature TEXT PRIMARY KEY,
                    transaction_hash TEXT NOT NULL,
                    accepted_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT INTO configuration (key, value_json) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                """,
                ("expected_signature", json.dumps(expected_signature)),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def accept(self, transaction: str) -> str:
        import hashlib

        try:
            decoded = base64.b64decode(transaction, validate=True)
        except ValueError:
            decoded = transaction.encode()
        digest = f"sha256:{hashlib.sha256(decoded).hexdigest()}"
        expected_signature = self.configuration().get(
            "expected_signature",
            self.expected_signature,
        )
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO accepted_transactions (
                    signature, transaction_hash, accepted_count
                ) VALUES (?, ?, 1)
                ON CONFLICT(signature) DO UPDATE SET
                    accepted_count = accepted_count + 1
                """,
                (expected_signature, digest),
            )
        return expected_signature

    def accepted(self, signature: str) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT 1 FROM accepted_transactions WHERE signature = ?",
                (signature,),
            ).fetchone()
        return row is not None

    def metrics(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM accepted_transactions ORDER BY signature"
            ).fetchall()
        return {"accepted_transactions": [dict(row) for row in rows]}

    def configure(self, value: dict[str, Any]) -> None:
        allowed = {
            "expected_signature",
            "accounts",
            "block_height",
            "latest_blockhash",
            "last_valid_block_height",
            "signature_status_mode",
        }
        if set(value) - allowed:
            raise ValueError("unknown upstream configuration")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            for key, child in value.items():
                connection.execute(
                    """
                    INSERT INTO configuration (key, value_json) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                    """,
                    (
                        key,
                        json.dumps(
                            child,
                            ensure_ascii=False,
                            allow_nan=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )

    def configuration(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT key, value_json FROM configuration").fetchall()
        return {row["key"]: json.loads(row["value_json"]) for row in rows}


class UpstreamServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], store: UpstreamStore):
        super().__init__(address, UpstreamHandler)
        self.store = store


class UpstreamHandler(BaseHTTPRequestHandler):
    server: UpstreamServer

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True})
        elif self.path == "/metrics":
            self._send(200, self.server.store.metrics())
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send(400, {"error": "invalid_json"})
            return
        if self.path == "/control":
            try:
                if not isinstance(value, dict):
                    raise ValueError
                self.server.store.configure(value)
            except (TypeError, ValueError):
                self._send(400, {"error": "invalid_control"})
                return
            self._send(200, {"ok": True})
            return
        method = value.get("method")
        request_id = value.get("id")
        configuration = self.server.store.configuration()
        if method == "sendTransaction":
            signature = self.server.store.accept(value["params"][0])
            result: Any = signature
        elif method == "getSignatureStatuses":
            signature = value["params"][0][0]
            status_mode = configuration.get("signature_status_mode", "accepted")
            status = (
                {
                    "slot": 123456,
                    "confirmations": None,
                    "err": None,
                    "confirmationStatus": "finalized",
                }
                if status_mode == "confirmed"
                or (status_mode == "accepted" and self.server.store.accepted(signature))
                else None
            )
            result = {"context": {"slot": 123456}, "value": [status]}
        elif method == "getBlockHeight":
            result = configuration.get("block_height", 90)
        elif method == "getGenesisHash":
            result = "11111111111111111111111111111111"
        elif method == "getLatestBlockhash":
            result = {
                "context": {"slot": 88},
                "value": {
                    "blockhash": configuration.get(
                        "latest_blockhash",
                        "11111111111111111111111111111111",
                    ),
                    "lastValidBlockHeight": configuration.get(
                        "last_valid_block_height",
                        100,
                    ),
                },
            }
        elif method == "getAccountInfo":
            account = configuration.get("accounts", {}).get(value["params"][0])
            result = {"value": account}
        elif method == "simulateTransaction":
            result = {
                "context": {"slot": 89},
                "value": {
                    "err": None,
                    "logs": ["Program Tokenkeg success"],
                    "preBalances": [10000, 1, 1, 1],
                    "postBalances": [5000, 1, 1, 1],
                    "accounts": [],
                    "unitsConsumed": 1714,
                    "fee": 5000,
                },
            }
        else:
            self._send(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "method not found"},
                },
            )
            return
        self._send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send(self, status: int, value: Any) -> None:
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--signature", required=True)
    args = parser.parse_args(argv)
    server = UpstreamServer(
        ("127.0.0.1", args.port),
        UpstreamStore(args.database, args.signature),
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
