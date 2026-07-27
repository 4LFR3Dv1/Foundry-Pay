"""Generate reproducible FC-GOV-001 governance evidence."""

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

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "evidence/runs/FC-GOV-001"
BASELINE = "8975a4b3edfae070919d68afe851652eb1f71ea8"
IMPLEMENTATION_COMMIT = "3cbf61ee819ac1277202d94c062f93f250c6412d"
SCHEMA = ROOT / "contracts/governance/component-maturity.schema.json"
EXAMPLE = ROOT / "contracts/governance/examples/fc-proto-007-self-validated.json"

sys.path.insert(0, str(ROOT / "scripts"))
from check_maturity_authorization import validate_record  # noqa: E402


def _dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
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
    completed = subprocess.run(
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
    return sorted(line for line in completed.stdout.splitlines() if line)


def generate(junit_source: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    record = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    schema_errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(record)
    )
    semantic_errors = validate_record(record)
    if schema_errors or semantic_errors:
        raise RuntimeError(
            f"governance record failed: schema={schema_errors}, semantic={semantic_errors}"
        )

    changed_paths = _changed_paths()
    forbidden_prefixes = (
        "packages/channel-protocol/",
        "contracts/channel/",
        "tests/channels/conformance/",
        "evidence/runs/FC-PROTO-007/",
    )
    forbidden_changes = [path for path in changed_paths if path.startswith(forbidden_prefixes)]
    if forbidden_changes:
        raise RuntimeError(f"FC-PROTO-007 or normative protocol paths changed: {forbidden_changes}")

    pytest_destination = RUN / "pytest-full.xml"
    shutil.copyfile(junit_source, pytest_destination)
    counts = _pytest_counts(pytest_destination)
    if counts["failures"] or counts["errors"]:
        raise RuntimeError(f"full regression failed: {counts}")

    _dump(
        RUN / "validation-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "baseline_commit": BASELINE,
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "policy": {
                "applies_program_wide": True,
                "previous_fc_proto_007_gate_recorded": True,
                "external_review_inferred": False,
                "work_item_done_implies_external_review": False,
                "work_item_done_implies_deployment_authorization": False,
            },
            "fc_proto_007_example": {
                "implementation": "complete",
                "self_validation": "passed",
                "external_review": "not_performed",
                "local_validator": "allowed",
                "devnet_fixture": "blocked",
                "mainnet": "blocked",
                "real_value": "blocked",
            },
            "schema": {
                "draft": "2020-12",
                "structurally_valid": True,
                "example_valid": True,
                "semantic_validation": "passed",
            },
            "tests": counts,
            "changed_paths": changed_paths,
            "forbidden_protocol_changes": forbidden_changes,
            "claims_excluded": [
                "external review performed",
                "ChannelVault implemented",
                "devnet authorized",
                "mainnet authorized",
                "real-value use authorized",
                "production readiness",
            ],
        },
    )

    manifest_paths = [
        RUN / "README.md",
        RUN / "TASK_CONTRACT.yaml",
        RUN / "generate_evidence.py",
        RUN / "pytest-full.xml",
        RUN / "validation-report.json",
        ROOT / ".agents/tasks/FC-GOV-001.yaml",
        SCHEMA,
        EXAMPLE,
        ROOT / "docs/channels/MATURITY_AND_AUTHORIZATION.md",
        ROOT / "docs/channels/ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md",
        ROOT / "scripts/check_maturity_authorization.py",
        ROOT / "tests/channels/test_maturity_authorization.py",
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
                for path in sorted(manifest_paths)
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
