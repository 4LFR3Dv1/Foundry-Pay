from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-005"


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_validation_report_preserves_claim_boundaries() -> None:
    report = load("validation-report.json")
    assert report["rust_tests"] == 7
    assert report["property_cases"] == 512
    assert report["violations"] == 0
    assert report["activated_rights_rewritable"] is False
    assert report["pause_preserves_exits"] is True
    assert report["automatic_active_channel_migration"] is False
    assert report["external_review"] == "not_performed"
    assert report["solana_loader_tested"] is False
    assert report["deployed_build_reproduced"] is False
    assert report["deployment_authorized"] is False


def test_artifact_manifest_recalculates() -> None:
    manifest = load("artifact-manifest.json")
    assert manifest["implementation_commit"] == ("8664401ba6f9367986960b3049340c7a90966ce2")
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["bytes"]
        assert "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]


def test_evidence_generator_is_reproducible() -> None:
    subprocess.run(
        [
            sys.executable,
            str(EVIDENCE / "generate_evidence.py"),
            "--baseline",
            "4642fac08e137ab991e13dc2ca743c008609f191",
            "--implementation-commit",
            "8664401ba6f9367986960b3049340c7a90966ce2",
        ],
        cwd=ROOT,
        check=True,
    )
    test_artifact_manifest_recalculates()
