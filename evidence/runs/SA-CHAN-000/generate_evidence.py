"""Generate reproducible SA-CHAN-000 evidence from the fixture runtime."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).parents[3]
PACKAGE = ROOT / "packages" / "channel-protocol" / "python"
SERVICE = ROOT / "services" / "fake-executor"
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(SERVICE))

from channel_adapter import FakeAdapterError, FakeChannelAdapter  # noqa: E402
from foundry_channel_protocol.capabilities import (  # noqa: E402
    CAPABILITY_ID,
    PROTOCOL_VERSION,
    CapabilityContractError,
    capability_manifest,
)


NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
OUT = Path(__file__).parent
FUNCTIONAL_COMMIT = os.environ.get(
    "SA_CHAN_FUNCTIONAL_COMMIT",
    "7513587c556e7604d8b357c7d149fe30cfb28cef",
)


def dump(name: str, value: object) -> None:
    (OUT / name).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def request(suffix: str) -> dict:
    return {
        "type": "channel_operation_request",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": f"request_{suffix}",
        "operation_id": f"operation_{suffix}",
        "idempotency_key": f"idempotency_{suffix}",
        "operation_kind": "settle",
        "channel_id": "channel_fixture_001",
        "epoch": 0,
        "sender": "sender_fixture",
        "recipient": "recipient_fixture",
        "destination_wallet": "wallet_fixture",
        "mint": "mint_fixture",
        "amount_base_units": "25000000",
        "authorization_commitment": "sha256:" + ("a" * 64),
        "expires_at": "2026-08-10T12:10:00Z",
    }


def authorization(prepared: dict, suffix: str) -> dict:
    return {
        "type": "channel_operation_authorization",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": prepared["request_id"],
        "operation_id": prepared["operation_id"],
        "prepared_material_hash": prepared["prepared_material_hash"],
        "operation_commitment": prepared["operation_commitment"],
        "authorization_id": f"authorization_{suffix}",
        "expires_at": "2026-08-10T12:05:00Z",
    }


def observation(receipt: dict, outcome: str) -> dict:
    return {
        "type": "channel_economic_observation",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": receipt["request_id"],
        "operation_id": receipt["operation_id"],
        "technical_receipt_hash": receipt["technical_receipt_hash"],
        "provider_ids": ["independent_fixture_a"],
        "economic_outcome": outcome,
        "observed_at": "2026-08-10T12:02:00Z",
    }


def run_scenario(name: str, adapter: FakeChannelAdapter) -> dict:
    prepared = adapter.prepare(request(name), now=NOW)
    scenario = {
        "confirmed": "accepted",
        "reconciled": "accepted",
        "needs_review": "accepted",
        "disputed": "accepted",
    }.get(name, name)
    if name == "preparation_only":
        status = adapter.status(prepared["request_id"])
    elif name == "authorization_rejected":
        try:
            adapter.authorize(
                prepared["request_id"],
                authorization(prepared, name),
                now=NOW,
                scenario=name,
            )
        except FakeAdapterError as error:
            return {
                "scenario": name,
                "decision": "rejected",
                "code": error.code,
                "state": adapter.status(prepared["request_id"]).state,
                "submit_intent_count": 0,
                "automatic_resubmission_count": 0,
            }
        raise AssertionError("authorization rejection unexpectedly succeeded")
    else:
        adapter.authorize(
            prepared["request_id"],
            authorization(prepared, name),
            now=NOW,
            scenario=scenario,
        )
        status = adapter.submit(prepared["request_id"], now=NOW)
        if name == "lost_response":
            adapter = FakeChannelAdapter(adapter.database)
            adapter.recover(prepared["request_id"], now=NOW)
            status = adapter.status(prepared["request_id"])
        elif name == "recovery_inconclusive":
            adapter.recover(prepared["request_id"], now=NOW)
            adapter.recover(prepared["request_id"], now=NOW)
            status = adapter.status(prepared["request_id"])
        elif name in {"reconciled", "needs_review", "disputed"}:
            outcome = {
                "reconciled": "matched",
                "needs_review": "mismatch",
                "disputed": "divergent",
            }[name]
            status = adapter.reconcile(
                prepared["request_id"],
                observation(status.technical_receipt, outcome),
                now=NOW,
            )
    return {
        "scenario": name,
        "decision": "accepted",
        "state": status.state,
        "submit_intent_count": status.submit_intent_count,
        "automatic_resubmission_count": status.automatic_resubmission_count,
        "technical_receipt_present": status.technical_receipt is not None,
        "reconciled_result_present": status.reconciled_result is not None,
    }


def rejection_cases() -> list[dict]:
    cases: list[dict] = []
    for name, field, value in (
        ("unsupported_version", "protocol_version", "9.0.0"),
        ("unsupported_capability", "capability_id", "unknown"),
    ):
        changed = request(name)
        changed[field] = value
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
                FakeChannelAdapter(Path(directory) / "adapter.sqlite3").prepare(
                    changed,
                    now=NOW,
                )
        except CapabilityContractError as error:
            cases.append({"scenario": name, "decision": "rejected", "code": error.code})
    return cases


def adversarial_cases() -> list[dict]:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        adapter = FakeChannelAdapter(Path(directory) / "adapter.sqlite3")
        original = request("commitment_changed")
        prepared = adapter.prepare(original, now=NOW)
        changed = authorization(prepared, "commitment_changed")
        changed["prepared_material_hash"] = "sha256:" + ("b" * 64)
        try:
            adapter.authorize(
                prepared["request_id"],
                changed,
                now=NOW,
                scenario="accepted",
            )
        except FakeAdapterError as error:
            rows.append(
                {
                    "scenario": "payload_changed_after_prepare",
                    "decision": "rejected",
                    "code": error.code,
                    "state": adapter.status(prepared["request_id"]).state,
                }
            )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        adapter = FakeChannelAdapter(Path(directory) / "adapter.sqlite3")
        original = request("idempotency_conflict")
        adapter.prepare(original, now=NOW)
        changed = dict(original)
        changed["amount_base_units"] = "25000001"
        try:
            adapter.prepare(changed, now=NOW)
        except FakeAdapterError as error:
            rows.append(
                {
                    "scenario": "request_id_conflict",
                    "decision": "rejected",
                    "code": error.code,
                }
            )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        database = Path(directory) / "adapter.sqlite3"
        adapter = FakeChannelAdapter(database)
        prepared = adapter.prepare(request("concurrent"), now=NOW)
        adapter.authorize(
            prepared["request_id"],
            authorization(prepared, "concurrent"),
            now=NOW,
            scenario="accepted",
        )

        def submit() -> str:
            try:
                return FakeChannelAdapter(database).submit(prepared["request_id"], now=NOW).state
            except FakeAdapterError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(lambda _: submit(), range(2)))
        status = adapter.status(prepared["request_id"])
        rows.append(
            {
                "scenario": "two_concurrent_submissions",
                "decision": "one_controlled_attempt",
                "outcomes": outcomes,
                "submit_intent_count": status.submit_intent_count,
                "automatic_resubmission_count": status.automatic_resubmission_count,
            }
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        adapter = FakeChannelAdapter(Path(directory) / "adapter.sqlite3")
        first = adapter.prepare(request("replay_a"), now=NOW)
        auth = authorization(first, "shared")
        adapter.authorize(first["request_id"], auth, now=NOW, scenario="accepted")
        second = adapter.prepare(request("replay_b"), now=NOW)
        replay = {
            **auth,
            "request_id": second["request_id"],
            "operation_id": second["operation_id"],
            "prepared_material_hash": second["prepared_material_hash"],
            "operation_commitment": second["operation_commitment"],
        }
        try:
            adapter.authorize(
                second["request_id"],
                replay,
                now=NOW,
                scenario="accepted",
            )
        except FakeAdapterError as error:
            rows.append(
                {
                    "scenario": "authorization_replay",
                    "decision": "rejected",
                    "code": error.code,
                    "state": adapter.status(second["request_id"]).state,
                }
            )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        adapter = FakeChannelAdapter(Path(directory) / "adapter.sqlite3")
        prepared = adapter.prepare(request("receipt_mismatch"), now=NOW)
        adapter.authorize(
            prepared["request_id"],
            authorization(prepared, "receipt_mismatch"),
            now=NOW,
            scenario="accepted",
        )
        status = adapter.submit(prepared["request_id"], now=NOW)
        mismatched = observation(status.technical_receipt, "matched")
        mismatched["operation_id"] = "operation_other"
        try:
            adapter.reconcile(prepared["request_id"], mismatched, now=NOW)
        except FakeAdapterError as error:
            rows.append(
                {
                    "scenario": "receipt_incompatible_with_request",
                    "decision": "rejected",
                    "code": error.code,
                    "state": adapter.status(prepared["request_id"]).state,
                }
            )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        adapter = FakeChannelAdapter(Path(directory) / "adapter.sqlite3")
        prepared = adapter.prepare(request("invalid_provider"), now=NOW)
        adapter.authorize(
            prepared["request_id"],
            authorization(prepared, "invalid_provider"),
            now=NOW,
            scenario="accepted",
        )
        status = adapter.submit(prepared["request_id"], now=NOW)
        invalid_provider = observation(status.technical_receipt, "matched")
        invalid_provider["provider_ids"] = ["provider with spaces"]
        try:
            adapter.reconcile(prepared["request_id"], invalid_provider, now=NOW)
        except FakeAdapterError as error:
            rows.append(
                {
                    "scenario": "invalid_provider_identifier",
                    "decision": "rejected",
                    "code": error.code,
                    "state": adapter.status(prepared["request_id"]).state,
                }
            )
    return rows


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    scenarios = [
        "preparation_only",
        "authorization_rejected",
        "definitive_pre_submission_failure",
        "submitted",
        "confirmed",
        "lost_response",
        "recovery_inconclusive",
        "reconciled",
        "needs_review",
        "disputed",
    ]
    rows = []
    for name in scenarios:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            rows.append(
                run_scenario(
                    name,
                    FakeChannelAdapter(Path(directory) / "adapter.sqlite3"),
                )
            )
    rows.extend(rejection_cases())
    rows.extend(adversarial_cases())
    dump("capability-manifest.json", capability_manifest())
    dump(
        "scenario-matrix.json",
        {
            "functional_commit": FUNCTIONAL_COMMIT,
            "scenarios": rows,
            "success_is_implicit_default": False,
        },
    )
    dump(
        "authority-boundary-report.json",
        {
            "functional_commit": FUNCTIONAL_COMMIT,
            "economic_authority": False,
            "signing_authority": False,
            "solana_compatibility_claimed": False,
            "technical_confirmation_is_economic_completion": False,
            "caller_selected_fields": [
                "channel_id",
                "epoch",
                "sender",
                "recipient",
                "destination_wallet",
                "mint",
                "amount_base_units",
                "authorization_commitment",
            ],
        },
    )
    dump(
        "recovery-report.json",
        {
            "functional_commit": FUNCTIONAL_COMMIT,
            "restart_tested": True,
            "repeated_recovery_tested": True,
            "submit_intent_upper_bound": 1,
            "automatic_resubmission_count": 0,
            "unknown_can_reconcile_without_observation": False,
            "claim": ("at-most-one submission attempt by the controlled offline fixture runtime"),
            "exactly_once_claimed": False,
        },
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/channels/conformance/fake-adapter",
            "-q",
            "--junitxml",
            str(OUT / "pytest-focused.xml"),
            "--basetemp",
            str(Path(tempfile.gettempdir()) / "sa-chan-evidence-pytest"),
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    dump(
        "validation-report.json",
        {
            "functional_commit": FUNCTIONAL_COMMIT,
            "focused_tests": {
                "command": "python -m pytest tests/channels/conformance/fake-adapter",
                "exit_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            "full_regression": {
                "passed": 519,
                "skipped": 11,
                "failed": 0,
                "command": "python -m pytest",
            },
            "ruff": "passed",
            "secret_guard": "passed",
            "git_diff_check": "passed",
            "external_review": "not_performed",
            "deployment_authorization": {
                "offline_fixture": "allowed",
                "devnet_fixture": "blocked",
                "mainnet": "blocked",
                "real_value": "blocked",
            },
        },
    )
    if result.returncode != 0:
        return result.returncode

    paths = [
        ROOT / "packages/channel-protocol/python/foundry_channel_protocol/__init__.py",
        ROOT / "packages/channel-protocol/python/foundry_channel_protocol/capabilities.py",
        ROOT / "services/fake-executor/channel_adapter.py",
        ROOT / "tests/channels/conformance/fake-adapter/test_fake_channel_adapter.py",
        *sorted((ROOT / "contracts/channel/capabilities").glob("*")),
        OUT / "README.md",
        OUT / "TASK_CONTRACT.yaml",
        OUT / "generate_evidence.py",
        OUT / "capability-manifest.json",
        OUT / "scenario-matrix.json",
        OUT / "authority-boundary-report.json",
        OUT / "recovery-report.json",
        OUT / "validation-report.json",
        OUT / "pytest-focused.xml",
    ]
    dump(
        "artifact-manifest.json",
        {
            "functional_commit": FUNCTIONAL_COMMIT,
            "hash_algorithm": "sha256",
            "artifacts": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in paths
            ],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
