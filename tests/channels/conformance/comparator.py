"""Passive comparator for independent Foundry Channels runner outputs."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


IMPLEMENTATIONS = ("python", "typescript", "rust")
EXPECTED_RESULT_COUNT = 28


class ConformanceComparisonError(ValueError):
    """A runner stream or cross-language observation is incompatible."""


@dataclass(frozen=True)
class ComparedStreams:
    results: dict[str, list[dict[str, Any]]]
    report: dict[str, Any]


ROOT = Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConformanceComparisonError(f"{path}: expected object")
    return value


def _load_jsonl(
    path: Path,
    implementation: str,
    validator: Draft202012Validator,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line:
            raise ConformanceComparisonError(f"{path}:{line_number}: empty line")
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ConformanceComparisonError(f"{path}:{line_number}: malformed JSON") from error
        errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
        if errors:
            raise ConformanceComparisonError(
                f"{path}:{line_number}: schema rejection: {errors[0].message}"
            )
        if value["implementation"] != implementation:
            raise ConformanceComparisonError(
                f"{path}:{line_number}: expected {implementation}, got {value['implementation']}"
            )
        results.append(value)
    if len(results) != EXPECTED_RESULT_COUNT:
        raise ConformanceComparisonError(
            f"{path}: expected {EXPECTED_RESULT_COUNT} results, got {len(results)}"
        )
    vector_ids = [item["vector_id"] for item in results]
    if vector_ids != sorted(vector_ids):
        raise ConformanceComparisonError(f"{path}: results are not ordered by vector_id")
    if len(vector_ids) != len(set(vector_ids)):
        raise ConformanceComparisonError(f"{path}: duplicate vector_id")
    return results


def _expected_vectors(registry_root: Path) -> dict[str, dict[str, Any]]:
    manifest = _load_json(registry_root / "manifest.v1.json")
    expected: dict[str, dict[str, Any]] = {}
    for kind, key in (("positive", "positive_vectors"), ("negative", "negative_vectors")):
        for filename in manifest[key]:
            vector = _load_json(registry_root / kind / filename)
            vector_id = vector["vector_id"]
            if vector_id in expected:
                raise ConformanceComparisonError(f"duplicate expected vector {vector_id}")
            if kind == "positive":
                expected_hex = vector["canonical_utf8_hex"]
                expected_base64 = vector["canonical_utf8_base64"]
                if expected_hex is None:
                    expected_hex = vector["source_bytes_hex"]
                if expected_base64 is None:
                    expected_base64 = base64.b64encode(bytes.fromhex(expected_hex)).decode("ascii")
                expected[vector_id] = {
                    "vector_kind": "positive",
                    "decision": "accept",
                    "stage": "complete",
                    "code": "ok",
                    "canonical_utf8_hex": expected_hex,
                    "canonical_utf8_base64": expected_base64,
                    "byte_length": vector["byte_length"],
                    "sha256": vector["expected_sha256"],
                }
            else:
                expected[vector_id] = {
                    "vector_kind": "negative",
                    "decision": "reject",
                    "stage": vector["rejection_stage"],
                    "code": vector["expected_rejection_code"],
                }
    if len(expected) != EXPECTED_RESULT_COUNT:
        raise ConformanceComparisonError(
            f"registry expected {EXPECTED_RESULT_COUNT} vectors, got {len(expected)}"
        )
    return expected


def _expected_runtime_versions(toolchains_path: Path) -> dict[str, str]:
    toolchains = _load_json(toolchains_path)
    return {
        entry["implementation"]: entry["runtime"]["version"]
        for entry in toolchains["implementations"]
    }


def compare_streams(
    *,
    registry_root: Path,
    schema_path: Path,
    toolchains_path: Path,
    stream_paths: dict[str, Path],
    enforce_toolchains: bool = True,
) -> ComparedStreams:
    if set(stream_paths) != set(IMPLEMENTATIONS):
        raise ConformanceComparisonError(
            "exactly python, typescript, and rust streams are required"
        )
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)
    expected = _expected_vectors(registry_root)
    runtime_versions = _expected_runtime_versions(toolchains_path)
    results = {
        implementation: _load_jsonl(stream_paths[implementation], implementation, validator)
        for implementation in IMPLEMENTATIONS
    }
    observed_ids = {tuple(item["vector_id"] for item in stream) for stream in results.values()}
    if len(observed_ids) != 1:
        raise ConformanceComparisonError("runner vector sets or order differ")

    mismatches: list[dict[str, Any]] = []
    for implementation, stream in results.items():
        if enforce_toolchains:
            observed_versions = {item["runtime_version"] for item in stream}
            if observed_versions != {runtime_versions[implementation]}:
                mismatches.append(
                    {
                        "implementation": implementation,
                        "field": "runtime_version",
                        "expected": runtime_versions[implementation],
                        "observed": sorted(observed_versions),
                    }
                )
        for item in stream:
            vector_id = item["vector_id"]
            expected_result = expected.get(vector_id)
            if expected_result is None:
                mismatches.append(
                    {
                        "implementation": implementation,
                        "vector_id": vector_id,
                        "field": "vector_id",
                        "expected": "registered",
                        "observed": "extra",
                    }
                )
                continue
            for field, expected_value in expected_result.items():
                if item.get(field) != expected_value:
                    mismatches.append(
                        {
                            "implementation": implementation,
                            "vector_id": vector_id,
                            "field": field,
                            "expected": expected_value,
                            "observed": item.get(field),
                        }
                    )
    if mismatches:
        raise ConformanceComparisonError(json.dumps(mismatches, sort_keys=True))

    return ComparedStreams(
        results=results,
        report={
            "schema_version": 1,
            "status": "passed",
            "implementations": list(IMPLEMENTATIONS),
            "positive_vectors": 8,
            "negative_vectors": 20,
            "result_count_per_implementation": EXPECTED_RESULT_COUNT,
            "agreement": {
                "positive_bytes_lengths_hashes": True,
                "negative_stages_codes": True,
            },
            "toolchains_enforced": enforce_toolchains,
        },
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--streams-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--no-enforce-toolchains", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _parse_args()
    try:
        compared = compare_streams(
            registry_root=ROOT / "contracts/channel/canonicalization",
            schema_path=ROOT / "contracts/channel/conformance/runner-result.v1.schema.json",
            toolchains_path=ROOT / "contracts/channel/conformance/toolchains.v1.json",
            stream_paths={
                implementation: arguments.streams_dir / f"{implementation}-results.jsonl"
                for implementation in IMPLEMENTATIONS
            },
            enforce_toolchains=not arguments.no_enforce_toolchains,
        )
    except ConformanceComparisonError as error:
        print(f"conformance comparison failed: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(compared.report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
