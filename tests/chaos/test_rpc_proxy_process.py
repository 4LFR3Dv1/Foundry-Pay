from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Iterator

from services.chaos_proxy import ChaosProxyStore

ROOT = Path(__file__).parents[2]
SIGNATURE = "proxy-test-signature-" + "s" * 64


def _port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
        return json.loads(response.read())


def _post(url: str, value: dict) -> dict:
    payload = json.dumps(value, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:  # noqa: S310
        return json.loads(response.read())


def _wait(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"process exited early: {process.returncode}")
        try:
            if _get(url).get("ok") is True:
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    raise RuntimeError(f"process did not become healthy: {url}")


@contextmanager
def _processes(tmp_path: Path) -> Iterator[tuple[str, str, Path, Path]]:
    upstream_port = _port()
    proxy_port = _port()
    upstream_database = tmp_path / "upstream.sqlite3"
    proxy_database = tmp_path / "proxy.sqlite3"
    common = {
        "cwd": ROOT,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
        "creationflags": _creation_flags(),
    }
    upstream = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "services.process_chaos.emulated_upstream",
            "--port",
            str(upstream_port),
            "--database",
            str(upstream_database),
            "--signature",
            SIGNATURE,
        ],
        **common,
    )
    proxy = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "services.chaos_proxy",
            "--port",
            str(proxy_port),
            "--upstream",
            f"http://127.0.0.1:{upstream_port}/",
            "--database",
            str(proxy_database),
        ],
        **common,
    )
    upstream_url = f"http://127.0.0.1:{upstream_port}"
    proxy_url = f"http://127.0.0.1:{proxy_port}"
    try:
        _wait(f"{upstream_url}/health", upstream)
        _wait(f"{proxy_url}/health", proxy)
        yield proxy_url, upstream_url, proxy_database, upstream_database
    finally:
        for process in (proxy, upstream):
            if process.poll() is None:
                process.terminate()
        for process in (proxy, upstream):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _send_request() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",
        "params": ["c2lnbmVk", {"encoding": "base64", "maxRetries": 0}],
    }


def test_proxy_forwards_and_persists_independent_counters(tmp_path: Path) -> None:
    with _processes(tmp_path) as (proxy, upstream, database, _):
        response = _post(proxy + "/", _send_request())
        assert response["result"] == SIGNATURE
        metrics = _get(proxy + "/metrics")
        upstream_metrics = _get(upstream + "/metrics")

    send = next(item for item in metrics["methods"] if item["method"] == "sendTransaction")
    assert send["requests_received"] == 1
    assert send["upstream_requests_forwarded"] == 1
    assert send["upstream_responses_received"] == 1
    assert send["client_responses_delivered"] == 1
    assert upstream_metrics["accepted_transactions"][0]["accepted_count"] == 1
    assert ChaosProxyStore(database).events()


def test_proxy_drops_response_only_after_upstream_acceptance(tmp_path: Path) -> None:
    with _processes(tmp_path) as (proxy, upstream, database, _):
        assert _post(
            proxy + "/control",
            {"method": "sendTransaction", "mode": "drop_after_upstream"},
        ) == {"ok": True}
        try:
            _post(proxy + "/", _send_request())
        except (
            RemoteDisconnected,
            ConnectionResetError,
            urllib.error.URLError,
        ):
            pass
        else:
            raise AssertionError("proxy should drop the client response")

        status = _post(
            proxy + "/",
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "getSignatureStatuses",
                "params": [[SIGNATURE], {"searchTransactionHistory": True}],
            },
        )
        metrics = _get(proxy + "/metrics")
        upstream_metrics = _get(upstream + "/metrics")

    assert status["result"]["value"][0]["confirmationStatus"] == "finalized"
    send = next(item for item in metrics["methods"] if item["method"] == "sendTransaction")
    assert send["requests_received"] == 1
    assert send["upstream_requests_forwarded"] == 1
    assert send["upstream_responses_received"] == 1
    assert send["client_responses_delivered"] == 0
    assert send["client_responses_dropped"] == 1
    assert upstream_metrics["accepted_transactions"][0]["accepted_count"] == 1
    ChaosProxyStore(database).events()


def test_definitive_rejection_never_reaches_upstream(tmp_path: Path) -> None:
    with _processes(tmp_path) as (proxy, upstream, _, _):
        _post(
            proxy + "/control",
            {"method": "sendTransaction", "mode": "reject_before_forward"},
        )
        response = _post(proxy + "/", _send_request())
        metrics = _get(proxy + "/metrics")
        upstream_metrics = _get(upstream + "/metrics")

    assert response["error"]["code"] == -32099
    send = next(item for item in metrics["methods"] if item["method"] == "sendTransaction")
    assert send["requests_received"] == 1
    assert send["upstream_requests_forwarded"] == 0
    assert send["rejected_before_forward"] == 1
    assert upstream_metrics["accepted_transactions"] == []
