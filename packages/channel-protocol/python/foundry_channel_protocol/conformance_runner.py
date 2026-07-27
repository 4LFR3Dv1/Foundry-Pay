"""Independent Python runner for frozen Foundry Channels conformance vectors."""

from __future__ import annotations

import argparse
import base64
import json
import platform
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn

from .canonical import (
    CanonicalizationError,
    canonical_json_bytes,
    parse_strict_json,
    sha256_raw_bytes,
    validate_amount_text,
    validate_canonical_set,
    validate_timestamp_text,
    validate_unsigned_integer,
    verify_declared_hash,
    verify_registered_domain,
    verify_self_hashed_record,
)


RUNNER_CONTRACT = "foundry.channels.conformance-runner-result/1"
RUNNER_VERSION = "1.0.0"
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")


def _reject(code: str, stage: str, path: str, detail: str) -> NoReturn:
    raise CanonicalizationError(code, stage, path, detail)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def _positive_source_bytes(vector: Mapping[str, Any]) -> bytes:
    profile_id = vector["profile_id"]
    if profile_id in {"raw-bytes-commitment-v1", "evidence-artifact-v1"}:
        source = vector.get("source_bytes_hex")
        if not isinstance(source, str):
            raise ValueError(f"{vector['vector_id']}: source_bytes_hex missing")
        return bytes.fromhex(source)

    source_json = vector.get("source_json")
    if not isinstance(source_json, str):
        raise ValueError(f"{vector['vector_id']}: source_json missing")
    source = parse_strict_json(source_json)
    if not isinstance(source, dict):
        raise ValueError(f"{vector['vector_id']}: source_json must contain an object")

    if profile_id == "signed-payload-v1":
        projection = source.get("payload")
        if not isinstance(projection, dict):
            raise ValueError(f"{vector['vector_id']}: signed payload missing")
    elif profile_id in {"self-hashed-record-v1", "journal-chain-v1"}:
        excluded = vector.get("excluded_fields")
        if not isinstance(excluded, list) or any(not isinstance(item, str) for item in excluded):
            raise ValueError(f"{vector['vector_id']}: invalid excluded_fields")
        missing = [field for field in excluded if field not in source]
        if missing:
            raise ValueError(f"{vector['vector_id']}: excluded field missing: {missing}")
        projection = {key: value for key, value in source.items() if key not in excluded}
    elif profile_id == "canonical-record-v1":
        projection = source
    else:
        raise ValueError(f"{vector['vector_id']}: unsupported profile {profile_id}")
    return canonical_json_bytes(projection)


def _validate_minimal_closed_object(value: Any) -> None:
    if not isinstance(value, dict):
        _reject("invalid_record", "schema", "$", "expected object")
    allowed = {"domain", "mint"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        _reject("unknown_field", "schema", f"$.{unknown[0]}", "field is not allowed")
    for field in ("domain", "mint"):
        if field not in value:
            _reject("missing_field", "schema", f"$.{field}", "required field is absent")


def _decode_lone_surrogate_fixture(value: Any) -> str:
    if value != "\\ud800":
        raise ValueError("lone-surrogate vector does not contain the frozen escape")
    return chr(0xD800)


def _exercise_negative(vector: Mapping[str, Any]) -> None:
    vector_id = vector["vector_id"]
    value = vector.get("input")
    if vector_id in {
        "duplicate-keys",
        "float",
        "nan",
        "infinity",
        "negative-zero",
        "null",
        "unsafe-integer",
    }:
        if not isinstance(value, str):
            raise ValueError(f"{vector_id}: string input required")
        parse_strict_json(value)
    elif vector_id in {"unknown-field", "missing-field"}:
        _validate_minimal_closed_object(value)
    elif vector_id == "bool-as-integer":
        validate_unsigned_integer(value, path="$.sequence")
    elif vector_id in {"u64-overflow", "amount-leading-zero"}:
        validate_amount_text(value, path="$.amount")
    elif vector_id == "malformed-timestamp":
        validate_timestamp_text(value, path="$.created_at")
    elif vector_id == "lone-surrogate":
        canonical_json_bytes({"value": _decode_lone_surrogate_fixture(value)})
    elif vector_id == "unregistered-domain":
        if not isinstance(value, str):
            raise ValueError("unregistered-domain: string input required")
        verify_registered_domain({"domain": value}, value)
    elif vector_id in {"uppercase-hash", "short-hash"}:
        verify_declared_hash(value, "sha256:" + "a" * 64)
    elif vector_id == "own-hash-in-preimage":
        verify_self_hashed_record(value, "receipt_hash")
    elif vector_id in {"canonical-set-order", "canonical-set-duplicate"}:
        validate_canonical_set(value, path="$.items")
    else:
        raise ValueError(f"{vector_id}: no independent negative executor")


def _base_result(vector_id: str, vector_kind: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "runner_contract": RUNNER_CONTRACT,
        "implementation": "python",
        "runtime_version": platform.python_version(),
        "runner_version": RUNNER_VERSION,
        "vector_id": vector_id,
        "vector_kind": vector_kind,
    }


def _run_positive(vector: Mapping[str, Any]) -> dict[str, Any]:
    payload = _positive_source_bytes(vector)
    return {
        **_base_result(str(vector["vector_id"]), "positive"),
        "decision": "accept",
        "stage": "complete",
        "code": "ok",
        "canonical_utf8_hex": payload.hex(),
        "canonical_utf8_base64": base64.b64encode(payload).decode("ascii"),
        "byte_length": len(payload),
        "sha256": sha256_raw_bytes(payload),
    }


def _run_negative(vector: Mapping[str, Any]) -> dict[str, Any]:
    try:
        _exercise_negative(vector)
    except CanonicalizationError as error:
        return {
            **_base_result(str(vector["vector_id"]), "negative"),
            "decision": "reject",
            "stage": error.stage,
            "code": error.code,
        }
    raise ValueError(f"{vector['vector_id']}: negative vector was accepted")


def run_registry(registry_root: Path) -> list[dict[str, Any]]:
    manifest = _load_json(registry_root / "manifest.v1.json")
    entries: list[tuple[str, str, Path]] = []
    for kind, key in (("positive", "positive_vectors"), ("negative", "negative_vectors")):
        names = manifest.get(key)
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError(f"manifest {key} must be an array of filenames")
        for name in names:
            path = registry_root / kind / name
            vector = _load_json(path)
            vector_id = vector.get("vector_id")
            if not isinstance(vector_id, str):
                raise ValueError(f"{path}: vector_id missing")
            entries.append((vector_id, kind, path))

    entries.sort(key=lambda item: item[0])
    vector_ids = [entry[0] for entry in entries]
    if len(vector_ids) != len(set(vector_ids)):
        raise ValueError("manifest contains duplicate vector_id")

    results = []
    for _, kind, path in entries:
        vector = _load_json(path)
        results.append(_run_positive(vector) if kind == "positive" else _run_negative(vector))
    return results


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        results = run_registry(args.registry_root)
    except Exception as error:
        print(f"python conformance runner failed: {error}", file=sys.stderr)
        return 2
    for result in results:
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
