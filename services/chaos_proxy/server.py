"""Localhost JSON-RPC proxy with durable, controllable response faults."""

from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .store import ChaosProxyStore

MAX_BODY_BYTES = 4 * 1024 * 1024


class ChaosProxyServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        *,
        upstream: str,
        store: ChaosProxyStore,
    ):
        if address[0] not in {"127.0.0.1", "localhost"}:
            raise ValueError("chaos proxy must bind to localhost")
        super().__init__(address, ChaosProxyHandler)
        self.upstream = upstream
        self.store = store


class ChaosProxyHandler(BaseHTTPRequestHandler):
    server: ChaosProxyServer

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json_response(200, {"ok": True})
        elif self.path == "/metrics":
            self._json_response(200, self.server.store.metrics())
        elif self.path == "/events":
            self._json_response(200, {"events": self.server.store.events()})
        else:
            self._json_response(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_body()
        if body is None:
            return
        if self.path == "/control":
            self._configure(body)
            return
        if self.path != "/":
            self._json_response(404, {"error": "not_found"})
            return
        try:
            request = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(400, {"error": "invalid_json"})
            return
        method = request.get("method") if isinstance(request, dict) else None
        if not isinstance(method, str):
            self._json_response(400, {"error": "invalid_json_rpc"})
            return
        sequence = self.server.store.receive(method, body)
        rule = self.server.store.rule(method)
        if rule["mode"] == "drop_before_forward":
            self.server.store.transition(
                sequence,
                "client_response_dropped",
                "client_connection_dropped_before_forward",
            )
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            return
        if rule["mode"] == "reject_before_forward":
            response = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32099,
                        "message": "fault proxy definitive rejection",
                    },
                },
                separators=(",", ":"),
            ).encode()
            self.server.store.transition(
                sequence,
                "rejected_before_forward",
                "request_rejected_before_forward",
            )
            self._raw_response(200, response)
            return
        if rule["mode"] == "return_null_status":
            response = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"context": {"slot": 0}, "value": [None]},
                },
                separators=(",", ":"),
            ).encode()
            self.server.store.transition(
                sequence,
                "synthetic_response_delivered",
                "null_status_delivered",
            )
            self._raw_response(200, response)
            return

        self.server.store.transition(
            sequence,
            "forwarded",
            "request_forwarded",
        )
        try:
            upstream_response = _forward(self.server.upstream, body)
        except (OSError, urllib.error.URLError) as error:
            response = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32098,
                        "message": "upstream unavailable",
                    },
                },
                separators=(",", ":"),
            ).encode()
            self.server.store.transition(
                sequence,
                "upstream_responded",
                "upstream_transport_failed",
                response=str(error).encode(),
            )
            self.server.store.transition(
                sequence,
                "client_response_delivered",
                "upstream_error_delivered",
            )
            self._raw_response(502, response)
            return
        self.server.store.transition(
            sequence,
            "upstream_responded",
            "upstream_response_persisted",
            response=upstream_response,
        )
        if rule["mode"] == "delay_after_upstream":
            time.sleep(rule["delay_ms"] / 1000)
        if rule["mode"] == "drop_after_upstream":
            self.server.store.transition(
                sequence,
                "client_response_dropped",
                "client_response_intentionally_dropped",
            )
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            return
        self.server.store.transition(
            sequence,
            "client_response_delivered",
            "client_response_delivered",
        )
        self._raw_response(200, upstream_response)

    def _configure(self, body: bytes) -> None:
        try:
            value = json.loads(body)
            if not isinstance(value, dict) or set(value) - {
                "method",
                "mode",
                "delay_ms",
            }:
                raise ValueError
            self.server.store.configure(
                value["method"],
                value["mode"],
                delay_ms=value.get("delay_ms", 0),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._json_response(400, {"error": "invalid_control"})
            return
        self._json_response(200, {"ok": True})

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY_BYTES:
            self._json_response(413, {"error": "invalid_body_size"})
            return None
        return self.rfile.read(length)

    def _json_response(self, status: int, value: Any) -> None:
        self._raw_response(
            status,
            json.dumps(value, separators=(",", ":"), sort_keys=True).encode(),
        )

    def _raw_response(self, status: int, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()

    def log_message(self, format: str, *args: Any) -> None:
        return


def _forward(upstream: str, payload: bytes) -> bytes:
    request = urllib.request.Request(
        upstream,
        data=payload,
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def run_server(
    *,
    host: str,
    port: int,
    upstream: str,
    database: Path,
) -> None:
    server = ChaosProxyServer(
        (host, port),
        upstream=upstream,
        store=ChaosProxyStore(database),
    )
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry-chaos-proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--database", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_server(
        host=args.host,
        port=args.port,
        upstream=args.upstream,
        database=args.database,
    )
    return 0
