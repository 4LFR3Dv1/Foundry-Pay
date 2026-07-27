"""Run and compare the three independent FC-PROTO-007 implementations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from comparator import ConformanceComparisonError, compare_streams


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "contracts/channel/canonicalization"
CONFORMANCE = ROOT / "contracts/channel/conformance"
EVIDENCE = ROOT / "evidence/runs/FC-PROTO-007"
CHANNEL_PYTHON = ROOT / "packages/channel-protocol/python"
CHANNEL_TYPESCRIPT = ROOT / "packages/channel-protocol/typescript"
CHANNEL_RUST = ROOT / "packages/channel-protocol/rust"
IMPLEMENTATIONS = ("python", "typescript", "rust")


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr}"
        )
    return completed.stdout


def _commands(registry: Path) -> dict[str, tuple[list[str], dict[str, str] | None]]:
    python_environment = os.environ.copy()
    existing_pythonpath = python_environment.get("PYTHONPATH")
    python_environment["PYTHONPATH"] = str(CHANNEL_PYTHON) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    typescript_entry = (
        CHANNEL_TYPESCRIPT / "dist/packages/channel-protocol/typescript/src/conformance-runner.js"
    )
    return {
        "python": (
            [
                sys.executable,
                "-m",
                "foundry_channel_protocol.conformance_runner",
                "--registry-root",
                str(registry),
            ],
            python_environment,
        ),
        "typescript": (
            ["node", str(typescript_entry), "--registry-root", str(registry)],
            None,
        ),
        "rust": (
            [
                "cargo",
                "run",
                "--quiet",
                "--locked",
                "--manifest-path",
                str(CHANNEL_RUST / "Cargo.toml"),
                "--",
                "--registry-root",
                str(registry),
            ],
            None,
        ),
    }


def run_implementations(registry: Path, output_root: Path) -> dict[str, Path]:
    streams: dict[str, Path] = {}
    for implementation, (command, environment) in _commands(registry).items():
        output = _run(command, env=environment)
        path = output_root / f"{implementation}-results.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8", newline="\n")
        streams[implementation] = path
    return streams


def _poison_registry(source: Path, destination: Path) -> dict[str, int]:
    shutil.copytree(source, destination)
    manifest = json.loads((destination / "manifest.v1.json").read_text(encoding="utf-8"))
    positive_count = 0
    negative_count = 0
    for filename in manifest["positive_vectors"]:
        path = destination / "positive" / filename
        vector = json.loads(path.read_text(encoding="utf-8"))
        vector["canonical_utf8_hex"] = "00"
        vector["canonical_utf8_base64"] = "AA=="
        vector["byte_length"] = 1
        vector["expected_sha256"] = "sha256:" + "0" * 64
        _dump(path, vector)
        positive_count += 1
    for filename in manifest["negative_vectors"]:
        path = destination / "negative" / filename
        vector = json.loads(path.read_text(encoding="utf-8"))
        vector["rejection_stage"] = "schema"
        vector["expected_rejection_code"] = "poisoned_expectation"
        _dump(path, vector)
        negative_count += 1
    return {"positive_vectors": positive_count, "negative_vectors": negative_count}


def _streams_are_identical(left: dict[str, Path], right: dict[str, Path]) -> bool:
    return all(
        left[implementation].read_bytes() == right[implementation].read_bytes()
        for implementation in IMPLEMENTATIONS
    )


def run(*, output_root: Path, enforce_toolchains: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    streams = run_implementations(REGISTRY, output_root)
    comparison = compare_streams(
        registry_root=REGISTRY,
        schema_path=CONFORMANCE / "runner-result.v1.schema.json",
        toolchains_path=CONFORMANCE / "toolchains.v1.json",
        stream_paths=streams,
        enforce_toolchains=enforce_toolchains,
    )

    with tempfile.TemporaryDirectory(prefix="fc-proto-007-poison-") as temporary:
        temporary_root = Path(temporary)
        poisoned_registry = temporary_root / "registry"
        poison_counts = _poison_registry(REGISTRY, poisoned_registry)
        poisoned_streams = run_implementations(
            poisoned_registry,
            temporary_root / "runner-output",
        )
        streams_unchanged = _streams_are_identical(streams, poisoned_streams)
        comparator_rejected_poison = False
        try:
            compare_streams(
                registry_root=poisoned_registry,
                schema_path=CONFORMANCE / "runner-result.v1.schema.json",
                toolchains_path=CONFORMANCE / "toolchains.v1.json",
                stream_paths=poisoned_streams,
                enforce_toolchains=enforce_toolchains,
            )
        except ConformanceComparisonError:
            comparator_rejected_poison = True
        if not streams_unchanged or not comparator_rejected_poison:
            raise RuntimeError(
                "expected-output poisoning gate failed: "
                f"streams_unchanged={streams_unchanged}, "
                f"comparator_rejected_poison={comparator_rejected_poison}"
            )

    poisoning_report = {
        "schema_version": 1,
        "status": "passed",
        "poisoned_fields": [
            "canonical_utf8_hex",
            "canonical_utf8_base64",
            "byte_length",
            "expected_sha256",
            "rejection_stage",
            "expected_rejection_code",
        ],
        "poisoned_vectors": poison_counts,
        "runner_streams_byte_identical": streams_unchanged,
        "comparator_rejected_poisoned_expectations": comparator_rejected_poison,
    }
    return comparison.report, poisoning_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=EVIDENCE)
    parser.add_argument(
        "--no-enforce-toolchains",
        action="store_true",
        help="permit local diagnostic runtimes; CI must never use this flag",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _parse_args()
    try:
        comparison, poisoning = run(
            output_root=arguments.output_root,
            enforce_toolchains=not arguments.no_enforce_toolchains,
        )
    except Exception as error:
        print(f"cross-language conformance failed: {error}", file=sys.stderr)
        return 2
    _dump(arguments.output_root / "comparison-report.json", comparison)
    _dump(arguments.output_root / "poisoning-report.json", poisoning)
    print(json.dumps({"comparison": comparison, "poisoning": poisoning}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
