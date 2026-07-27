"""Generate FC-CTRL-015 integration evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "evidence/runs/FC-CTRL-015"
BASELINE = "63da85549bcd247a0510e8af18cddc30d8c53bb2"
IMPLEMENTATION_COMMIT = "e464d4c03f873683aeca65b5d44297c2561b7077"

sys.path.insert(0, str(ROOT / "scripts"))
from check_maturity_authorization import validate_record  # noqa: E402


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
    maturity = json.loads((RUN / "fc-proto-007-maturity.json").read_text(encoding="utf-8"))
    maturity_errors = validate_record(maturity)
    if maturity_errors:
        raise RuntimeError(f"maturity record failed: {maturity_errors}")

    changed_paths = _changed_paths()
    forbidden_prefixes = (
        "packages/",
        "contracts/channel/",
        "evidence/runs/FC-PROTO-007/",
    )
    forbidden = [path for path in changed_paths if path.startswith(forbidden_prefixes)]
    if forbidden:
        raise RuntimeError(f"coordination changed implementation paths: {forbidden}")

    pytest_path = RUN / "pytest-full.xml"
    shutil.copyfile(junit_source, pytest_path)
    counts = _pytest_counts(pytest_path)
    if counts["failures"] or counts["errors"]:
        raise RuntimeError(f"regression failed: {counts}")

    _dump(
        RUN / "validation-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "baseline_commit": BASELINE,
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "fc_proto_007": {
                "pr": 34,
                "functional_head": "ef9a99949bae3d2088a7b51cd55ef4efb14124c7",
                "evidence_head": "5e4f7fff521f99c93a2e6b99bd8db8c9a8041649",
                "merge_commit": BASELINE,
                "main_ci_run": 30286605271,
                "main_ci_conclusion": "success",
            },
            "maturity": {
                "implementation": "complete",
                "self_validation": "passed",
                "external_review": "not_performed",
                "local_validator": "allowed",
                "devnet_fixture": "blocked",
                "mainnet": "blocked",
                "real_value": "blocked",
            },
            "next_gates": {
                "FC-SEC-002": "ready",
                "SA-CHAN-000": "blocked_pending_FC-SEC-002",
            },
            "tests": counts,
            "changed_paths": changed_paths,
            "forbidden_implementation_changes": forbidden,
        },
    )

    paths = [
        RUN / "README.md",
        RUN / "TASK_CONTRACT.yaml",
        RUN / "fc-proto-007-maturity.json",
        RUN / "generate_evidence.py",
        RUN / "pytest-full.xml",
        RUN / "validation-report.json",
        ROOT / ".agents/tasks/FC-CTRL-015.yaml",
        ROOT / "docs/channels/WORK_GRAPH.md",
        ROOT / "docs/channels/work-items.yaml",
        ROOT / "tests/channels/test_foundation_contracts.py",
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
