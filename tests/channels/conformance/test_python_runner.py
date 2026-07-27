from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CHANNEL_PYTHON = ROOT / "packages/channel-protocol/python"
sys.path.insert(0, str(CHANNEL_PYTHON))

from foundry_channel_protocol.conformance_runner import run_registry  # noqa: E402


REGISTRY = ROOT / "contracts/channel/canonicalization"


def test_python_runner_recomputes_all_frozen_vectors() -> None:
    results = run_registry(REGISTRY)
    assert len(results) == 28
    assert [item["vector_id"] for item in results] == sorted(item["vector_id"] for item in results)
    positives = {item["vector_id"]: item for item in results if item["vector_kind"] == "positive"}
    negatives = {item["vector_id"]: item for item in results if item["vector_kind"] == "negative"}
    assert len(positives) == 8
    assert len(negatives) == 20

    manifest = json.loads((REGISTRY / "manifest.v1.json").read_text(encoding="utf-8"))
    for filename in manifest["positive_vectors"]:
        vector = json.loads((REGISTRY / "positive" / filename).read_text(encoding="utf-8"))
        observed = positives[vector["vector_id"]]
        expected_hex = vector["canonical_utf8_hex"] or vector["source_bytes_hex"]
        assert observed["canonical_utf8_hex"] == expected_hex
        if vector["canonical_utf8_base64"] is not None:
            assert observed["canonical_utf8_base64"] == vector["canonical_utf8_base64"]
        assert observed["byte_length"] == vector["byte_length"]
        assert observed["sha256"] == vector["expected_sha256"]
    for filename in manifest["negative_vectors"]:
        vector = json.loads((REGISTRY / "negative" / filename).read_text(encoding="utf-8"))
        observed = negatives[vector["vector_id"]]
        assert observed["stage"] == vector["rejection_stage"]
        assert observed["code"] == vector["expected_rejection_code"]
