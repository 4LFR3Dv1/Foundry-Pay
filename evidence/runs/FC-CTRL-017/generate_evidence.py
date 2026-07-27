"""Generate FC-CTRL-017 governance evidence from executed tests."""

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
RUN = ROOT / "evidence/runs/FC-CTRL-017"
BASELINE = "c73ab47bb80364392d601f1f5ed9e00aa217f3b8"
IMPLEMENTATION_COMMIT = "0ee8db60c73dce4a916fe129f28b86d3287d8005"


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


def generate(junit_source: Path) -> None:
    changed_paths = _changed_paths()
    allowed = {
        ".agents/tasks/FC-CTRL-017.yaml",
        ".agents/tasks/FC-SEC-002.yaml",
        "docs/channels/EVIDENCE_INDEX.md",
        "docs/channels/WORK_GRAPH.md",
        "docs/channels/security/FC-SEC-002-CONTRACT.md",
        "docs/channels/work-items.yaml",
        "tests/channels/test_foundation_contracts.py",
    }
    unauthorized = [path for path in changed_paths if path not in allowed]
    if unauthorized:
        raise RuntimeError(f"unauthorized paths: {unauthorized}")

    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    security = next(item for item in work_items if item["id"] == "FC-SEC-002")
    required_invariants = {
        "rejected mutations create no economic effect or authority advancement",
        "durable rejection audit effects are permitted but never confer authority",
    }
    if not required_invariants.issubset(set(security["invariants"])):
        raise RuntimeError("effect taxonomy is not frozen in FC-SEC-002")

    pytest_path = RUN / "pytest-full.xml"
    shutil.copyfile(junit_source, pytest_path)
    counts = _pytest_counts(pytest_path)
    if counts["failures"] or counts["errors"]:
        raise RuntimeError(f"regression failed: {counts}")

    _dump(
        RUN / "effect-taxonomy.json",
        {
            "schema_version": 1,
            "forbidden_effects": [
                "economic_effect",
                "verified",
                "activation_requested",
                "authorized",
                "completed",
            ],
            "permitted_audit_effects": ["issued", "rejected", "rejection_event"],
            "audit_effect_confers_authority": False,
        },
    )
    _dump(
        RUN / "validation-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "baseline_commit": BASELINE,
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "changed_paths": changed_paths,
            "unauthorized_changes": unauthorized,
            "external_review": "not_performed",
            "tests": counts,
        },
    )

    paths = [
        ROOT / ".agents/tasks/FC-CTRL-017.yaml",
        ROOT / ".agents/tasks/FC-SEC-002.yaml",
        ROOT / "docs/channels/EVIDENCE_INDEX.md",
        ROOT / "docs/channels/WORK_GRAPH.md",
        ROOT / "docs/channels/security/FC-SEC-002-CONTRACT.md",
        ROOT / "docs/channels/work-items.yaml",
        ROOT / "tests/channels/test_foundation_contracts.py",
        RUN / "README.md",
        RUN / "TASK_CONTRACT.yaml",
        RUN / "effect-taxonomy.json",
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
