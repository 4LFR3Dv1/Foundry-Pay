"""Cross-repository real-process chaos matrix."""

from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from foundry_external_execution_protocol import canonicalize, sha256_digest

from services.chaos_proxy import ChaosProxyStore
from services.reconciliation import (
    SourceDescriptor,
    SourceRegistry,
    aggregate_reconciliation,
)
from services.reconciliation.backfill import backfill_fp_e2e_001

GATEWAY_SCENARIOS = (
    "kill_before_broadcast",
    "kill_after_broadcast_intent",
    "kill_during_send_transaction",
    "response_lost_after_acceptance",
    "definitive_rejection",
    "not_found_after_expiry",
    "replay_after_restart",
    "concurrent_gateways",
)


def _port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise RuntimeError("process endpoint returned a non-object")
    return value


def _wait(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read().decode() if process.stderr else ""
            raise RuntimeError(f"process exited early: {process.returncode}: {stderr}")
        try:
            if _get(url).get("ok") is True:
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    raise RuntimeError(f"process did not become healthy: {url}")


def _stop(*processes: subprocess.Popen[bytes]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _run_gateway_scenario(
    *,
    scenario: str,
    scenario_root: Path,
    foundry_root: Path,
    solana_agent_root: Path,
) -> dict[str, Any]:
    upstream_port = _port()
    proxy_port = _port()
    upstream_database = scenario_root / "upstream.sqlite3"
    proxy_database = scenario_root / "proxy.sqlite3"
    process_options = {
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
            "initial-signature",
        ],
        cwd=foundry_root,
        **process_options,
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
        cwd=foundry_root,
        **process_options,
    )
    upstream_url = f"http://127.0.0.1:{upstream_port}"
    proxy_url = f"http://127.0.0.1:{proxy_port}"
    try:
        _wait(upstream_url + "/health", upstream)
        _wait(proxy_url + "/health", proxy)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "gateway.chaos_scenario",
                "--scenario",
                scenario,
                "--workspace",
                str(scenario_root / "gateway"),
                "--proxy-endpoint",
                proxy_url,
                "--upstream-control",
                upstream_url + "/control",
                "--upstream-metrics",
                upstream_url + "/metrics",
            ],
            cwd=solana_agent_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            creationflags=_creation_flags(),
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Solana-Agent scenario failed ({scenario}): {completed.stderr}")
        result = json.loads(completed.stdout)
        result["proxy_event_chain"] = ChaosProxyStore(proxy_database).events()
        result["proxy_event_chain_head"] = result["proxy_event_chain"][-1]["event_hash"]
        return result
    finally:
        _stop(proxy, upstream)


def _source_convergence(foundry_root: Path) -> dict[str, Any]:
    proof = foundry_root / "evidence" / "runs" / "FP-E2E-001" / "live-proof.json"
    expected, l1, l1_descriptor = backfill_fp_e2e_001(proof)
    l2 = json.loads(
        (foundry_root / "evidence" / "runs" / "FP-REC-001" / "l2-observation.json").read_text(
            encoding="utf-8"
        )
    )
    l2_descriptor = SourceDescriptor(
        **{
            field: l2[field]
            for field in (
                "source_id",
                "source_class",
                "source_kind",
                "provider_id",
                "trust_domain_id",
                "endpoint_identity_hash",
                "parser_id",
            )
        }
    )
    registry = SourceRegistry([l1_descriptor, l2_descriptor])
    pending = aggregate_reconciliation(
        expected,
        [l1],
        registry,
        unavailable_source_ids=[l2_descriptor.source_id],
    )
    converged = aggregate_reconciliation(expected, [l1, l2], registry)
    history = [
        {
            "sequence": 1,
            "event": "l2_unavailable",
            "result": pending,
            "result_hash": sha256_digest(canonicalize(pending)),
        },
        {
            "sequence": 2,
            "event": "l2_converged",
            "result": converged,
            "result_hash": sha256_digest(canonicalize(converged)),
        },
    ]
    return {
        "type": "real_process_chaos_result",
        "protocol_version": "1.0.0",
        "scenario": "source_unavailable_then_converged",
        "execution_request_id": expected["execution_request_id"],
        "initial_reconciliation_status": pending["reconciliation_status"],
        "initial_independent_verification": pending["independent_verification"],
        "final_reconciliation_status": converged["reconciliation_status"],
        "final_independent_verification": converged["independent_verification"],
        "history_preserved": True,
        "history": history,
        "private_material_persisted": False,
    }


def run_process_matrix(
    *,
    foundry_root: Path,
    solana_agent_root: Path,
) -> dict[str, dict[str, Any]]:
    if not (solana_agent_root / "gateway" / "chaos_scenario.py").is_file():
        raise RuntimeError("Solana-Agent SA-CHAOS-001 checkout is required")
    results: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="fp-fail-002-") as temporary:
        root = Path(temporary)
        for scenario in GATEWAY_SCENARIOS:
            scenario_root = root / scenario
            scenario_root.mkdir()
            results[scenario] = _run_gateway_scenario(
                scenario=scenario,
                scenario_root=scenario_root,
                foundry_root=foundry_root,
                solana_agent_root=solana_agent_root,
            )
    results["source_unavailable_then_converged"] = _source_convergence(foundry_root)
    return results


def _send_count(report: dict[str, Any]) -> int:
    metrics = report.get("proxy_send_transaction")
    return metrics["requests_received"] if isinstance(metrics, dict) else 0


def write_process_evidence(
    *,
    foundry_root: Path,
    solana_agent_root: Path,
    output_directory: Path,
    foundry_implementation_commit: str,
    solana_agent_implementation_commit: str,
) -> None:
    results = run_process_matrix(
        foundry_root=foundry_root,
        solana_agent_root=solana_agent_root,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, str]] = []
    for scenario, report in sorted(results.items()):
        path = output_directory / f"{scenario}.json"
        payload = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        path.write_bytes(payload)
        artifacts.append({"path": path.name, "sha256": sha256_digest(payload)})
    artifact_root = sha256_digest(canonicalize(artifacts))
    journal_root = {
        "type": "external_journal_checkpoint",
        "protocol_version": "1.0.0",
        "work_item": "FP-FAIL-002",
        "foundry_implementation_commit": foundry_implementation_commit,
        "solana_agent_implementation_commit": solana_agent_implementation_commit,
        "artifact_root": artifact_root,
        "artifacts": artifacts,
    }
    root_payload = (
        json.dumps(journal_root, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    (output_directory / "journal-root.json").write_bytes(root_payload)
    demo = copy.deepcopy(results["response_lost_after_acceptance"])
    demo["demo_assertions"] = {
        "send_transaction_requests_received": _send_count(demo),
        "upstream_requests_forwarded": demo["proxy_send_transaction"][
            "upstream_requests_forwarded"
        ],
        "client_responses_delivered": demo["proxy_send_transaction"]["client_responses_delivered"],
        "gateway_recovery_outcome": demo["recovery_response"]["result"]["outcome"],
        "rebroadcasts": _send_count(demo) - 1,
    }
    (output_directory / "master-demo.json").write_text(
        json.dumps(demo, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "work_item": "FP-FAIL-002",
        "scenario_count": len(results),
        "gateway_process_scenario_count": len(GATEWAY_SCENARIOS),
        "all_send_transaction_counts_at_most_one": all(
            _send_count(report) <= 1 for report in results.values()
        ),
        "journal_root": sha256_digest(root_payload),
        "artifact_root": artifact_root,
        "master_demo": "master-demo.json",
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
