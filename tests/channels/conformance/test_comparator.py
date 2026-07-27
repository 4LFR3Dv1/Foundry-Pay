from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]
CHANNEL_PYTHON = ROOT / "packages/channel-protocol/python"
sys.path.insert(0, str(CHANNEL_PYTHON))

from foundry_channel_protocol.conformance_runner import run_registry  # noqa: E402

from .comparator import ConformanceComparisonError, compare_streams  # noqa: E402


REGISTRY = ROOT / "contracts/channel/canonicalization"
CONFORMANCE = ROOT / "contracts/channel/conformance"


def _write_stream(
    path: Path,
    implementation: str,
    results: list[dict[str, Any]],
    *,
    runtime_version: str,
) -> None:
    rows = []
    for result in results:
        row = copy.deepcopy(result)
        row["implementation"] = implementation
        row["runtime_version"] = runtime_version
        rows.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture
def streams(tmp_path: Path) -> dict[str, Path]:
    results = run_registry(REGISTRY)
    versions = {
        "python": "3.11.9",
        "typescript": "24.15.0",
        "rust": "1.85.1",
    }
    paths = {}
    for implementation, version in versions.items():
        path = tmp_path / f"{implementation}.jsonl"
        _write_stream(path, implementation, results, runtime_version=version)
        paths[implementation] = path
    return paths


def _compare(streams: dict[str, Path]) -> None:
    compare_streams(
        registry_root=REGISTRY,
        schema_path=CONFORMANCE / "runner-result.v1.schema.json",
        toolchains_path=CONFORMANCE / "toolchains.v1.json",
        stream_paths=streams,
    )


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _replace_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_comparator_accepts_exact_cross_language_agreement(streams: dict[str, Path]) -> None:
    _compare(streams)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "out_of_order", "malformed"])
def test_comparator_rejects_invalid_stream_shape(
    streams: dict[str, Path],
    mutation: str,
) -> None:
    path = streams["typescript"]
    rows = _load_rows(path)
    if mutation == "missing":
        rows.pop()
        _replace_rows(path, rows)
    elif mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[-2])
        _replace_rows(path, rows)
    elif mutation == "out_of_order":
        rows[0], rows[1] = rows[1], rows[0]
        _replace_rows(path, rows)
    else:
        path.write_text("{bad json}\n", encoding="utf-8")
    with pytest.raises(ConformanceComparisonError):
        _compare(streams)


def test_comparator_rejects_positive_byte_mismatch(streams: dict[str, Path]) -> None:
    path = streams["rust"]
    rows = _load_rows(path)
    positive = next(row for row in rows if row["vector_kind"] == "positive")
    positive["canonical_utf8_hex"] = "00"
    _replace_rows(path, rows)
    with pytest.raises(ConformanceComparisonError):
        _compare(streams)


@pytest.mark.parametrize(
    "field,value",
    [("stage", "domain_verification"), ("code", "wrong_code")],
)
def test_comparator_rejects_negative_semantic_mismatch(
    streams: dict[str, Path],
    field: str,
    value: str,
) -> None:
    path = streams["python"]
    rows = _load_rows(path)
    negative = next(row for row in rows if row["vector_kind"] == "negative")
    negative[field] = value
    _replace_rows(path, rows)
    with pytest.raises(ConformanceComparisonError):
        _compare(streams)


def test_comparator_rejects_toolchain_mismatch(streams: dict[str, Path]) -> None:
    path = streams["typescript"]
    rows = _load_rows(path)
    rows[0]["runtime_version"] = "0.0.0"
    _replace_rows(path, rows)
    with pytest.raises(ConformanceComparisonError):
        _compare(streams)
