"""Normative low-level canonicalization and SHA-256 primitives for Channels v1.

Object-specific modules remain responsible for closed schemas, projections,
authority, and economic validation. This module never infers a projection.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

import rfc8785


JSON_SAFE_UNSIGNED_MAX = 9_007_199_254_740_991
U64_MAX = 18_446_744_073_709_551_615
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_EXPLICIT_DOMAINS = frozenset(
    {
        "foundry.channels.voucher",
        "foundry.channels.recipient-binding",
        "foundry.channels.recipient-binding-journal",
        "foundry.channels.voucher-ledger-scope",
    }
)
_TYPE_DOMAINS = {
    "foundry.channels.channel-snapshot": "channel",
    "foundry.channels.settlement-request": "settlement_request",
    "foundry.channels.settlement-execution-commitment": "settlement_execution_commitment",
    "foundry.channels.settlement-authorization": "execution_authorization",
    "foundry.channels.settlement-observation": "settlement_observation",
    "foundry.channels.reconciled-settlement-receipt": "reconciled_settlement_receipt",
    "foundry.channels.recovery-record": "settlement_recovery_record",
    "foundry.channels.settlement-journal-entry": "settlement_journal_entry",
    "foundry.channels.closure-request": "channel_closure_request",
    "foundry.channels.closure-request-snapshot": "closure_snapshot_at_request",
    "foundry.channels.closure-freeze": "closure_snapshot_at_freeze",
    "foundry.channels.refund-request": "refund_request",
    "foundry.channels.refund-projection": "refund_projection",
    "foundry.channels.refund-execution-commitment": "refund_execution_commitment",
    "foundry.channels.technical-refund-receipt": "technical_refund_receipt",
    "foundry.channels.refund-observation": "channel_refund_observation",
    "foundry.channels.reconciled-refund": "reconciled_channel_refund",
    "foundry.channels.epoch-transition-eligibility": "epoch_transition_eligibility",
    "foundry.channels.refund-journal-entry": "refund_journal_entry",
}
REGISTERED_DOMAINS = frozenset(_EXPLICIT_DOMAINS | _TYPE_DOMAINS.keys())


class CanonicalizationError(ValueError):
    """Stable fail-closed error with a conformance stage and code."""

    def __init__(self, code: str, stage: str, path: str, detail: str) -> None:
        self.code = code
        self.stage = stage
        self.path = path
        self.detail = detail
        super().__init__(f"{stage}:{code} at {path}: {detail}")


def _reject(code: str, stage: str, path: str, detail: str) -> NoReturn:
    raise CanonicalizationError(code, stage, path, detail)


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None:
        _reject("null_forbidden", "projection", path, "optional values must be omitted")
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if not 0 <= value <= JSON_SAFE_UNSIGNED_MAX:
            _reject(
                "unsafe_integer",
                "projection",
                path,
                f"expected unsigned integer <= {JSON_SAFE_UNSIGNED_MAX}",
            )
        return
    if isinstance(value, float):
        _reject("float_forbidden", "projection", path, "floating-point values are forbidden")
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            _reject("lone_surrogate", "canonicalization", path, "invalid Unicode scalar value")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                _reject("non_string_key", "projection", path, "object keys must be strings")
            _validate_json_value(key, f"{path}.<key>")
            _validate_json_value(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_value(child, f"{path}[{index}]")
        return
    _reject(
        "unsupported_json_type",
        "projection",
        path,
        f"unsupported {type(value).__name__}",
    )


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _reject("duplicate_key", "parse", f"$.{key}", "property appears more than once")
        result[key] = value
    return result


def _reject_float(value: str) -> NoReturn:
    code = "negative_zero" if value in {"-0.0", "-0e0", "-0E0"} else "float_forbidden"
    _reject(code, "parse", "$", f"JSON number {value!r} is not an integer")


def _parse_integer(value: str) -> int:
    if value == "-0":
        _reject("negative_zero", "parse", "$", "negative zero is forbidden")
    parsed = int(value)
    if not 0 <= parsed <= JSON_SAFE_UNSIGNED_MAX:
        _reject(
            "unsafe_integer",
            "parse",
            "$",
            f"expected unsigned integer <= {JSON_SAFE_UNSIGNED_MAX}",
        )
    return parsed


def _reject_constant(value: str) -> NoReturn:
    _reject("non_finite_number", "parse", "$", f"{value} is forbidden")


def parse_strict_json(value: str | bytes) -> Any:
    """Parse one UTF-8 JSON value while retaining duplicate-key evidence."""

    if isinstance(value, bytes):
        try:
            source = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            _reject("invalid_utf8", "parse", "$", str(error))
    elif isinstance(value, str):
        source = value
    else:
        _reject("invalid_wire_type", "parse", "$", "expected str or bytes")
    try:
        parsed = json.loads(
            source,
            object_pairs_hook=_pairs_without_duplicates,
            parse_float=_reject_float,
            parse_int=_parse_integer,
            parse_constant=_reject_constant,
        )
    except CanonicalizationError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        _reject("malformed_json", "parse", "$", str(error))
    _validate_json_value(parsed)
    return parsed


def canonical_json_bytes(validated_projection: Any) -> bytes:
    """Return RFC 8785 bytes for an already selected normative projection."""

    _validate_json_value(validated_projection)
    try:
        return rfc8785.dumps(validated_projection)
    except (rfc8785.CanonicalizationError, rfc8785.FloatDomainError) as error:
        _reject("jcs_rejected", "canonicalization", "$", str(error))


def sha256_raw_bytes(value: bytes) -> str:
    """Return the canonical textual SHA-256 digest of exact bytes."""

    if not isinstance(value, bytes):
        _reject("invalid_bytes", "hash", "$", "expected bytes")
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def sha256_canonical_json(validated_projection: Any) -> str:
    """Hash the exact JCS bytes of an explicit validated projection."""

    return sha256_raw_bytes(canonical_json_bytes(validated_projection))


def verify_declared_hash(value: str, expected: str) -> None:
    """Fail closed unless both hashes are canonical and exactly equal."""

    for candidate, path in ((value, "$.declared_hash"), (expected, "$.expected_hash")):
        if not isinstance(candidate, str) or _HASH.fullmatch(candidate) is None:
            _reject("invalid_hash", "hash_verification", path, "expected lowercase sha256")
    if value != expected:
        _reject("hash_mismatch", "hash_verification", "$", "declared hash differs")


def unsigned_record_projection(
    record: Mapping[str, Any],
    own_hash_field: str,
) -> dict[str, Any]:
    """Exclude exactly one declared own-hash field from a closed record."""

    if not isinstance(record, Mapping):
        _reject("invalid_record", "projection", "$", "expected object")
    if not isinstance(own_hash_field, str) or not own_hash_field:
        _reject("invalid_hash_field", "projection", "$", "expected explicit field name")
    if own_hash_field not in record:
        _reject(
            "own_hash_missing",
            "projection",
            f"$.{own_hash_field}",
            "self-hashed record must contain its own hash",
        )
    return {key: value for key, value in record.items() if key != own_hash_field}


def verify_self_hashed_record(
    record: Mapping[str, Any],
    own_hash_field: str,
) -> dict[str, Any]:
    """Verify one self-hashed record and return its exact unsigned projection."""

    projection = unsigned_record_projection(record, own_hash_field)
    declared = record[own_hash_field]
    verify_declared_hash(declared, sha256_canonical_json(projection))
    return projection


def validate_canonical_set(values: Sequence[str], *, path: str) -> list[str]:
    """Validate a lexicographically sorted unique string set without repairing it."""

    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        _reject("invalid_canonical_set", "projection", path, "expected an array of strings")
    if len(values) != len(set(values)):
        _reject("canonical_set_duplicate", "projection", path, "elements must be unique")
    if values != sorted(values):
        _reject(
            "canonical_set_order",
            "projection",
            path,
            "elements must already be lexicographically sorted",
        )
    return list(values)


def validate_amount_text(value: Any, *, path: str, u64: bool = True) -> str:
    """Validate a canonical unsigned decimal economic value."""

    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        _reject("invalid_amount", "schema", path, "expected canonical unsigned decimal")
    if u64 and int(value) > U64_MAX:
        _reject("amount_out_of_range", "schema", path, "expected unsigned 64-bit value")
    return value


def validate_unsigned_integer(
    value: Any,
    *,
    path: str,
    maximum: int = JSON_SAFE_UNSIGNED_MAX,
) -> int:
    """Reject booleans, coercions, negatives, and integers above a declared bound."""

    if type(value) is not int or not 0 <= value <= maximum:
        _reject(
            "invalid_integer",
            "schema",
            path,
            f"expected unsigned integer <= {maximum}",
        )
    return value


def validate_timestamp_text(value: Any, *, path: str) -> str:
    """Validate exact UTC second precision and calendar validity."""

    from datetime import datetime

    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        _reject("invalid_timestamp", "schema", path, "expected YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        _reject("invalid_timestamp", "schema", path, str(error))
    return value


def verify_registered_domain(projection: Mapping[str, Any], expected_domain: str) -> None:
    """Require one exact registered domain binding; prefix matching is forbidden."""

    if expected_domain not in REGISTERED_DOMAINS:
        _reject("domain_unregistered", "domain_verification", "$.domain", expected_domain)
    if expected_domain in _EXPLICIT_DOMAINS:
        if projection.get("domain") != expected_domain:
            _reject("domain_mismatch", "domain_verification", "$.domain", expected_domain)
        return
    expected_type = _TYPE_DOMAINS[expected_domain]
    if projection.get("type") != expected_type or projection.get("protocol_version") != "1.0.0":
        _reject(
            "domain_mismatch",
            "domain_verification",
            "$",
            f"expected type={expected_type!r}, protocol_version='1.0.0'",
        )
