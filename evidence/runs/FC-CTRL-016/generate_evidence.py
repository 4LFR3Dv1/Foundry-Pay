"""Generate FC-CTRL-016 governance evidence from executed tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "evidence/runs/FC-CTRL-016"
BASELINE = "4a1ce934b7d3a3d95772f9546128c1afc591e36e"
IMPLEMENTATION_COMMIT = "a2660e202e68808bf654fca5e2b4bd1752d2a206"


def _dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _pytest_counts(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        field: sum(int(suite.attrib.get(field, "0")) for suite in suites)
        for field in ("tests", "failures", "errors", "skipped")
    }


def _changed_paths() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "diff",
            "--name-only",
            BASELINE,
            IMPLEMENTATION_COMMIT,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(result.stdout.splitlines())


def _security_projection() -> dict[str, Any]:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    security = next(item for item in work_items if item["id"] == "FC-SEC-002")
    expected_maturity = {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
    }
    expected_authorization = {
        "local_validator": "allowed",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }
    if security["status"] != "ready":
        raise RuntimeError("FC-SEC-002 is not ready")
    if security["maturity_gate"] != expected_maturity:
        raise RuntimeError("FC-SEC-002 maturity gate differs from frozen policy")
    if security["deployment_authorization"] != expected_authorization:
        raise RuntimeError("FC-SEC-002 authorization differs from frozen policy")
    return {
        "status": security["status"],
        "dependencies": security["dependencies"],
        "invariants": security["invariants"],
        "acceptance": security["acceptance"],
        "maturity_gate": security["maturity_gate"],
        "deployment_authorization": security["deployment_authorization"],
        "external_review_requirement": security["external_review_requirement"],
        "stop_conditions": security["stop_conditions"],
    }


def generate(junit_source: Path) -> None:
    changed_paths = _changed_paths()
    allowed = (
        ".agents/tasks/FC-CTRL-016.yaml",
        ".agents/tasks/FC-SEC-002.yaml",
        "docs/channels/EVIDENCE_INDEX.md",
        "docs/channels/WORK_GRAPH.md",
        "docs/channels/security/FC-SEC-002-CONTRACT.md",
        "docs/channels/work-items.yaml",
        "tests/channels/test_foundation_contracts.py",
    )
    forbidden = [path for path in changed_paths if path not in allowed]
    if forbidden:
        raise RuntimeError(f"coordination changed unauthorized paths: {forbidden}")

    pytest_path = RUN / "pytest-full.xml"
    shutil.copyfile(junit_source, pytest_path)
    counts = _pytest_counts(pytest_path)
    if counts["failures"] or counts["errors"]:
        raise RuntimeError(f"regression failed: {counts}")

    projection = _security_projection()
    _dump(RUN / "fc-sec-002-contract.json", projection)
    _dump(
        RUN / "validation-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "baseline_commit": BASELINE,
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "changed_paths": changed_paths,
            "unauthorized_changes": forbidden,
            "proof_classes": [
                "protocol_v1_replay_resistance",
                "cross_type_and_profile_collision_resistance",
                "version_lifecycle",
            ],
            "maturity": projection["maturity_gate"],
            "deployment_authorization": projection["deployment_authorization"],
            "external_review": "not_performed",
            "tests": counts,
        },
    )

    paths = [
        ROOT / ".agents/tasks/FC-CTRL-016.yaml",
        ROOT / ".agents/tasks/FC-SEC-002.yaml",
        ROOT / "docs/channels/EVIDENCE_INDEX.md",
        ROOT / "docs/channels/WORK_GRAPH.md",
        ROOT / "docs/channels/security/FC-SEC-002-CONTRACT.md",
        ROOT / "docs/channels/work-items.yaml",
        ROOT / "tests/channels/test_foundation_contracts.py",
        RUN / "README.md",
        RUN / "TASK_CONTRACT.yaml",
        RUN / "fc-sec-002-contract.json",
        RUN / "generate_evidence.py",
        RUN / "pytest-full.xml",
        RUN / "validation-report.json",
    ]
    _dump(
        RUN / "artifact-manifest.json",
        {
            "schema_version": 1,
            "algorithm": "sha256",
            "artifacts": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in sorted(paths)
            ],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit-source", type=Path, required=True)
    arguments = parser.parse_args()
    generate(arguments.junit_source.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
