from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/runs/FC-SEC-004"
CRATE = ROOT / "services/failure_lab/channel-concurrency"


def load(name: str) -> object:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def cargo() -> str:
    found = shutil.which("cargo")
    if found:
        return found
    suffix = ".exe" if os.name == "nt" else ""
    candidate = Path.home() / ".cargo/bin" / f"cargo{suffix}"
    assert candidate.exists(), "cargo is required for FC-SEC-004 self-validation"
    return str(candidate)


def test_race_matrix_has_serial_witnesses_and_no_violations() -> None:
    report = load("bounded-schedule-report.json")
    assert report["scenarios"] == 7
    assert report["schedules"] == 14
    assert report["violations"] == 0
    assert all(result["serial_witness"] for result in report["results"])
    assert all(result["conservation"] for result in report["results"])
    assert all(result["accepted_count"] <= 1 for result in report["results"])


def test_oversubscribed_settlement_and_deadline_races_fail_closed() -> None:
    report = load("bounded-schedule-report.json")
    oversubscribed = [
        result for result in report["results"] if result["scenario"] == "settle_30_vs_settle_30"
    ]
    assert len(oversubscribed) == 2
    assert all(result["accepted_count"] == 1 for result in oversubscribed)
    assert all(result["stale_count"] == 1 for result in oversubscribed)
    assert all(result["final_settled"] == 30 for result in oversubscribed)

    deadline = [
        result
        for result in report["results"]
        if result["scenario"] == "activation_pre_deadline_vs_refund_at_deadline"
    ]
    assert len(deadline) == 2
    assert all(result["final_activated"] == 40 for result in deadline)


def test_evidence_claims_remain_offline_and_narrow() -> None:
    validation = load("validation-report.json")
    assert validation["property_cases"] == 512
    assert validation["violations"] == 0
    assert validation["serial_witnesses"] == 14
    assert validation["solana_runtime_proved"] is False
    assert validation["formal_verification"] == "not_performed"
    assert validation["external_review"] == "not_performed"
    assert validation["deployment_authorization"]["local_validator"] == "blocked"
    assert validation["deployment_authorization"]["devnet_fixture"] == "blocked"
    assert validation["deployment_authorization"]["mainnet"] == "blocked"
    assert validation["deployment_authorization"]["real_value"] == "blocked"

    accounting = load("authority-and-accounting-report.json")
    assert accounting["commit_time_revalidation"] is True
    assert accounting["caller_affects_destination"] is False
    assert accounting["obligation_hash_affects_economics"] is False
    assert accounting["real_spl_balance_compared"] is False


def test_artifact_manifest_recalculates() -> None:
    manifest = load("artifact-manifest.json")
    assert manifest["implementation_commit"] == ("2458885917eb917e263538397a601f0c81a1e855")
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["bytes"]
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == artifact["sha256"]


def test_pinned_concurrency_model_reproduces() -> None:
    subprocess.run(
        [cargo(), "test", "--locked"],
        cwd=CRATE,
        check=True,
        capture_output=True,
        text=True,
    )
    with tempfile.TemporaryDirectory() as temporary:
        report_path = Path(temporary) / "schedules.json"
        subprocess.run(
            [
                cargo(),
                "run",
                "--locked",
                "--example",
                "schedule_explorer",
                "--",
                str(report_path),
            ],
            cwd=CRATE,
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schedules"] == 14
    assert report["violations"] == 0
