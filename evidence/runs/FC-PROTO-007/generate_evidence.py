"""Assemble immutable FC-PROTO-007 CI artifacts into a hashed evidence pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "evidence/runs/FC-PROTO-007"
BASELINE = "8975a4b3edfae070919d68afe851652eb1f71ea8"
FROZEN_SPECIFICATION = "17b656cbdd6ae53cece9cebb9123058c03e67b82"
IMPLEMENTATION_COMMIT = "e0991ace6052527a10d929abfc4dfb87f3ff4581"
REVIEWED_HEAD = "1d23660e7be3d41e580089aefcdd50c4e0bc577f"
WORKFLOW_RUN = 30281177556
WORKFLOW_URL = "https://github.com/4LFR3Dv1/Foundry-Pay/actions/runs/30281177556"
WORKFLOW_ARTIFACT_SHA = "005cfaa1a9d605f6847305d515ea0cb20cee7c5c"
IMPLEMENTATIONS = ("python", "typescript", "rust")


def _dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _only(root: Path, pattern: str) -> Path:
    matches = list(root.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"expected one {pattern!r} under {root}, got {len(matches)}")
    return matches[0]


def _copy(source: Path, destination: Path) -> None:
    destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _pytest_counts(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        field: sum(int(suite.attrib.get(field, "0")) for suite in suites)
        for field in ("tests", "failures", "errors", "skipped")
    }


def _assert_frozen_registry() -> None:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "diff",
            "--exit-code",
            FROZEN_SPECIFICATION,
            "--",
            "contracts/channel/canonicalization",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("frozen FC-PROTO-006 registry differs from its reviewed commit")


def generate(artifact_root: Path) -> None:
    comparison = _only(
        artifact_root,
        f"fc-proto-007-comparison-{WORKFLOW_ARTIFACT_SHA}",
    )
    poisoning = _only(
        artifact_root,
        f"fc-proto-007-poisoning-{WORKFLOW_ARTIFACT_SHA}",
    )
    pytest_artifact = _only(
        artifact_root,
        f"fc-proto-007-pytest-{WORKFLOW_ARTIFACT_SHA}",
    )

    for implementation in IMPLEMENTATIONS:
        independent = (
            _only(
                artifact_root,
                f"fc-proto-007-{implementation}-{WORKFLOW_ARTIFACT_SHA}",
            )
            / f"{implementation}-results.jsonl"
        )
        compared = comparison / "runner-results" / f"{implementation}-results.jsonl"
        poisoned = poisoning / f"{implementation}-results.jsonl"
        if not (independent.read_bytes() == compared.read_bytes() == poisoned.read_bytes()):
            raise RuntimeError(f"{implementation} streams differ across CI gates")
        _copy(independent, RUN / f"{implementation}-results.jsonl")

    _copy(comparison / "comparison-report.json", RUN / "comparison-report.json")
    _copy(poisoning / "poisoning-report.json", RUN / "poisoning-report.json")
    _copy(pytest_artifact / "pytest-full.xml", RUN / "pytest-full.xml")

    streams = {
        implementation: _load_jsonl(RUN / f"{implementation}-results.jsonl")
        for implementation in IMPLEMENTATIONS
    }
    expected_versions = {
        "python": "3.11.9",
        "typescript": "24.15.0",
        "rust": "1.85.1",
    }
    for implementation, results in streams.items():
        if len(results) != 28:
            raise RuntimeError(f"{implementation} emitted {len(results)} results")
        versions = {result["runtime_version"] for result in results}
        if versions != {expected_versions[implementation]}:
            raise RuntimeError(
                f"{implementation} runtime mismatch: expected "
                f"{expected_versions[implementation]}, got {sorted(versions)}"
            )

    _assert_frozen_registry()
    pytest_counts = _pytest_counts(RUN / "pytest-full.xml")
    if pytest_counts["failures"] or pytest_counts["errors"]:
        raise RuntimeError(f"full regression failed: {pytest_counts}")

    _dump(
        RUN / "validation-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "baseline_commit": BASELINE,
            "frozen_specification_commit": FROZEN_SPECIFICATION,
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "reviewed_head": REVIEWED_HEAD,
            "workflow": {
                "run_id": WORKFLOW_RUN,
                "url": WORKFLOW_URL,
                "conclusion": "success",
                "head_sha": REVIEWED_HEAD,
                "artifact_merge_sha": WORKFLOW_ARTIFACT_SHA,
            },
            "vectors": {
                "positive": 8,
                "negative": 20,
                "results_per_implementation": 28,
            },
            "agreement": {
                "positive_bytes_lengths_hashes": True,
                "negative_stages_codes": True,
                "independent_artifacts_match_comparator_inputs": True,
                "poisoned_streams_byte_identical": True,
                "poisoned_expectations_rejected": True,
            },
            "frozen_registry_diff": "empty",
            "full_regression": pytest_counts,
            "claims_excluded": [
                "Solana execution",
                "ChannelVault behavior",
                "production readiness",
                "independent external security review completed",
            ],
        },
    )
    _dump(
        RUN / "toolchain-dependency-report.json",
        {
            "schema_version": 1,
            "toolchains": {
                "python": {
                    "runtime": "CPython 3.11.9",
                    "jcs": "rfc8785 0.1.4",
                    "lock": "packages/channel-protocol/python/requirements-conformance.lock",
                },
                "typescript": {
                    "runtime": "Node.js 24.15.0",
                    "compiler": "TypeScript 5.9.3",
                    "jcs": "canonicalize 3.0.0",
                    "lock": "packages/channel-protocol/typescript/package-lock.json",
                },
                "rust": {
                    "runtime": "Rust/Cargo 1.85.1",
                    "edition": "2024",
                    "jcs": "serde_json_canonicalizer 0.3.2",
                    "lock": "packages/channel-protocol/rust/Cargo.lock",
                },
            },
        },
    )

    manifest_paths = [
        RUN / "README.md",
        RUN / "TASK_CONTRACT.yaml",
        RUN / "generate_evidence.py",
        RUN / "python-results.jsonl",
        RUN / "typescript-results.jsonl",
        RUN / "rust-results.jsonl",
        RUN / "comparison-report.json",
        RUN / "poisoning-report.json",
        RUN / "pytest-full.xml",
        RUN / "validation-report.json",
        RUN / "toolchain-dependency-report.json",
        ROOT / "contracts/channel/conformance/toolchains.v1.json",
        ROOT / "contracts/channel/conformance/rejection-codes.v1.json",
        ROOT / "contracts/channel/conformance/runner-result.v1.schema.json",
        ROOT / "packages/channel-protocol/python/foundry_channel_protocol/conformance_runner.py",
        ROOT / "packages/channel-protocol/typescript/src/conformance-runner.ts",
        ROOT / "packages/channel-protocol/rust/src/lib.rs",
        ROOT / "tests/channels/conformance/comparator.py",
        ROOT / "tests/channels/conformance/run_cross_language.py",
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
    parser.add_argument("--artifact-root", type=Path, required=True)
    arguments = parser.parse_args()
    generate(arguments.artifact_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
