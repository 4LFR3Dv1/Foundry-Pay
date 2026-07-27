"""Offline close, refund, and epoch-eligibility reference semantics.

The module operates only on caller-provided observations. It never asserts
that a refund happened on Solana. A technical receipt is retained as technical
evidence; only an independently matching observation produces a reconciled
economic receipt.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol

from foundry_external_execution_protocol import canonicalize, sha256_digest

from .channel import AccountingProjection, validate_channel


PROTOCOL_VERSION = "1.0.0"
ZERO_HASH = "sha256:" + ("0" * 64)
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PUBKEY = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_AMBIGUOUS_STATES = frozenset(
    {
        "submitted",
        "confirming",
        "reconciling",
        "needs_recovery",
        "needs_review",
        "disputed",
    }
)
_RELEASING_STATES = frozenset(
    {
        "rejected_before_submission",
        "failed_before_submission",
        "explicitly_cancelled_before_authorization",
        "completed",
    }
)
_REFUND_REASONS = frozenset({"post_claim_window_unallocated", "final_close"})
_CLOSURE_REQUEST_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "domain",
        "channel",
        "closure_id",
        "idempotency_key",
        "channel_snapshot_hash",
        "requested_at",
        "claim_deadline",
        "status",
        "request_hash",
    }
)
_REQUEST_SNAPSHOT_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "domain",
        "channel",
        "closure_id",
        "closure_request_hash",
        "channel_snapshot_hash",
        "funded_total_base_units",
        "activated_total_base_units",
        "settled_total_base_units",
        "refunded_total_base_units",
        "vault_balance_base_units",
        "outstanding_right_base_units",
        "unallocated_capacity_base_units",
        "latest_activated_sequence",
        "latest_activated_voucher_hash",
        "requested_at",
        "claim_deadline",
        "pre_deadline_refundable_base_units",
        "channel_status",
        "closure_phase",
        "request_snapshot_hash",
    }
)
_FREEZE_SNAPSHOT_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "domain",
        "channel",
        "closure_id",
        "request_snapshot_hash",
        "channel_snapshot_hash",
        "funded_total_base_units",
        "activated_total_base_units",
        "settled_total_base_units",
        "refunded_total_base_units",
        "vault_balance_base_units",
        "outstanding_right_base_units",
        "excess_refundable_base_units",
        "latest_activated_sequence",
        "latest_activated_voucher_hash",
        "claim_deadline",
        "frozen_at",
        "unresolved_operation_count",
        "channel_status",
        "closure_phase",
        "freeze_snapshot_hash",
    }
)
_REFUND_REQUEST_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "domain",
        "channel",
        "closure_id",
        "refund_id",
        "idempotency_key",
        "reason",
        "destination",
        "requested_base_units",
        "freeze_snapshot_hash",
        "created_at",
        "expires_at",
        "request_hash",
    }
)
_EXECUTION_COMMITMENT_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "refund_request_hash",
        "refund_projection_hash",
        "execution_request_id",
        "execution_commitment_hash",
        "prepared_message_hash",
        "executor_id",
        "expected_signer",
        "expires_at",
    }
)
_TECHNICAL_RECEIPT_REQUIRED = frozenset(
    {
        "type",
        "protocol_version",
        "refund_id",
        "refund_request_hash",
        "execution_request_id",
        "execution_commitment_hash",
        "outcome",
        "signature_status",
        "technical_status",
        "observed_at",
        "receipt_hash",
    }
)
_TECHNICAL_RECEIPT_FIELDS = _TECHNICAL_RECEIPT_REQUIRED | {"transaction_signature"}
_OBSERVATION_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "domain",
        "source_id",
        "channel_id",
        "channel_account",
        "epoch",
        "mint",
        "destination",
        "refund_id",
        "refund_request_hash",
        "refund_projection_hash",
        "transaction_signature",
        "funded_total_base_units",
        "activated_total_base_units",
        "settled_total_base_units",
        "refunded_total_before_base_units",
        "refunded_total_after_base_units",
        "vault_balance_before_base_units",
        "vault_balance_after_base_units",
        "observed_at",
        "observation_hash",
    }
)


class ClosureError(RuntimeError):
    """Stable fail-closed error for closure reference operations."""

    def __init__(self, code: str, field: str, detail: str) -> None:
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code} at {field}: {detail}")


class RefundObservationVerifier(Protocol):
    """Injected boundary for one independently sourced refund observation."""

    source_id: str

    def verify(self, observation: Mapping[str, Any]) -> bool: ...


@dataclass(frozen=True, slots=True)
class ClosureArtifacts:
    request: dict[str, Any]
    snapshot_at_request: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RefundRecord:
    refund_id: str
    request_hash: str
    projection_hash: str
    state: str
    submit_intent_count: int
    transaction_signature: str | None
    reconciled_receipt: dict[str, Any] | None


def _reject(code: str, field: str, detail: str) -> NoReturn:
    raise ClosureError(code, field, detail)


def _closed(
    value: Mapping[str, Any],
    *,
    field: str,
    required: frozenset[str],
    allowed: frozenset[str] | None = None,
) -> None:
    observed = set(value)
    permitted = required if allowed is None else allowed
    missing = sorted(required - observed)
    unknown = sorted(observed - permitted)
    if missing:
        _reject("missing_field", field, ", ".join(missing))
    if unknown:
        _reject("unknown_field", field, ", ".join(unknown))


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return sha256_digest(canonicalize(dict(value)))


def _with_hash(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = _canonical_hash(result)
    return result


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        _reject("invalid_hash", field, "expected sha256:<64 lowercase hex>")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _reject("invalid_identifier", field, "expected a closed protocol identifier")
    return value


def _pubkey(value: object, field: str) -> str:
    if not isinstance(value, str) or _PUBKEY.fullmatch(value) is None:
        _reject("invalid_pubkey", field, "expected a base58 public identifier")
    return value


def _validate_domain(value: object, field: str) -> None:
    if not isinstance(value, Mapping):
        _reject("invalid_type", field, "expected object")
    expected = {"environment", "network", "genesis_hash", "program_id"}
    if set(value) != expected:
        _reject("invalid_domain_shape", field, "expected closed domain fields")
    if value["environment"] != "devnet" or value["network"] != "solana:devnet":
        _reject("unsupported_domain", field, "expected Solana devnet")
    _pubkey(value["genesis_hash"], f"{field}.genesis_hash")
    _pubkey(value["program_id"], f"{field}.program_id")


def _validate_channel_reference(value: object, field: str) -> None:
    if not isinstance(value, Mapping):
        _reject("invalid_type", field, "expected object")
    expected = {"channel_id", "channel_account", "epoch", "sender", "mint"}
    if set(value) != expected:
        _reject("invalid_channel_reference_shape", field, "expected closed channel fields")
    _identifier(value["channel_id"], f"{field}.channel_id")
    _pubkey(value["channel_account"], f"{field}.channel_account")
    if type(value["epoch"]) is not int or value["epoch"] < 0:
        _reject("invalid_epoch", f"{field}.epoch", "expected non-negative integer")
    _pubkey(value["sender"], f"{field}.sender")
    _pubkey(value["mint"], f"{field}.mint")


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        _reject("invalid_timestamp", field, "expected UTC seconds in YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject("invalid_timestamp", field, "timestamp is not a real calendar time")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        _reject("naive_datetime", "now", "an aware datetime is required")
    return value.astimezone(UTC)


def _format_time(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _amount(value: object, field: str, *, positive: bool = False) -> int:
    if not isinstance(value, str) or not value.isdigit() or (len(value) > 1 and value[0] == "0"):
        _reject("invalid_amount", field, "expected an unsigned canonical decimal string")
    parsed = int(value)
    if positive and parsed <= 0:
        _reject("amount_must_be_positive", field, "must be greater than zero")
    if parsed > 18_446_744_073_709_551_615:
        _reject("amount_out_of_range", field, "expected an unsigned 64-bit integer")
    return parsed


def _operation_states(states: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(states)
    unsupported = sorted(set(normalized) - _AMBIGUOUS_STATES - _RELEASING_STATES)
    if unsupported:
        _reject("unsupported_operation_state", "operation_states", ", ".join(unsupported))
    return normalized


def _domain(channel: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "environment": channel["environment"],
        "network": channel["network"],
        "genesis_hash": channel["genesis_hash"],
        "program_id": channel["program_id"],
    }


def _channel_reference(channel: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "channel_id": channel["channel_id"],
        "channel_account": channel["channel_account"],
        "epoch": channel["epoch"],
        "sender": channel["sender"],
        "mint": channel["mint"],
    }


def _snapshot_hash(channel: Mapping[str, Any]) -> str:
    return _canonical_hash(channel)


def _validate_hash(value: Mapping[str, Any], field: str) -> None:
    supplied = _hash(value.get(field), field)
    unsigned = {key: child for key, child in value.items() if key != field}
    if _canonical_hash(unsigned) != supplied:
        _reject("artifact_tampering", field, "canonical hash mismatch")


def _validate_freeze_snapshot(value: Mapping[str, Any]) -> None:
    _closed(value, field="freeze_snapshot", required=_FREEZE_SNAPSHOT_FIELDS)
    _validate_hash(value, "freeze_snapshot_hash")
    if value.get("type") != "closure_snapshot_at_freeze":
        _reject("invalid_freeze_snapshot", "freeze_snapshot.type", "wrong object type")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        _reject("invalid_protocol_version", "freeze_snapshot.protocol_version", "unsupported")
    _validate_domain(value.get("domain"), "freeze_snapshot.domain")
    _validate_channel_reference(value.get("channel"), "freeze_snapshot.channel")
    funded = _amount(value.get("funded_total_base_units"), "freeze.funded")
    activated = _amount(value.get("activated_total_base_units"), "freeze.activated")
    settled = _amount(value.get("settled_total_base_units"), "freeze.settled")
    refunded = _amount(value.get("refunded_total_base_units"), "freeze.refunded")
    vault = _amount(value.get("vault_balance_base_units"), "freeze.vault")
    outstanding = _amount(value.get("outstanding_right_base_units"), "freeze.outstanding")
    excess = _amount(value.get("excess_refundable_base_units"), "freeze.excess_refundable")
    if funded != vault + settled + refunded:
        _reject("conservation_violation", "freeze_snapshot", "F must equal V + S + R")
    if not 0 <= settled <= activated <= funded - refunded:
        _reject("rights_bounds_violation", "freeze_snapshot", "requires 0 <= S <= A <= F - R")
    if outstanding != activated - settled:
        _reject("outstanding_right_mismatch", "freeze_snapshot", "must equal A - S")
    if excess != funded - refunded - activated:
        _reject("excess_refundable_mismatch", "freeze_snapshot", "must equal F - R - A")
    if value.get("channel_status") != "closing":
        _reject("freeze_lifecycle_forbidden", "freeze_snapshot.channel_status", "requires closing")
    if value.get("closure_phase") != "ready_to_finalize":
        _reject("freeze_phase_invalid", "freeze_snapshot.closure_phase", "requires freeze")
    if _time(value.get("frozen_at"), "freeze_snapshot.frozen_at") < _time(
        value.get("claim_deadline"),
        "freeze_snapshot.claim_deadline",
    ):
        _reject("claim_window_open", "freeze_snapshot.frozen_at", "precedes deadline")
    unresolved = value.get("unresolved_operation_count")
    if type(unresolved) is not int or unresolved < 0:
        _reject(
            "invalid_unresolved_operation_count",
            "freeze_snapshot.unresolved_operation_count",
            "expected non-negative integer",
        )


def _validate_request_snapshot(
    closure_request: Mapping[str, Any],
    value: Mapping[str, Any],
) -> tuple[int, int, int, int]:
    _closed(
        closure_request,
        field="closure_request",
        required=_CLOSURE_REQUEST_FIELDS,
    )
    _closed(
        value,
        field="snapshot_at_request",
        required=_REQUEST_SNAPSHOT_FIELDS,
    )
    _validate_hash(closure_request, "request_hash")
    _validate_hash(value, "request_snapshot_hash")
    if closure_request.get("type") != "channel_closure_request":
        _reject("invalid_closure_request", "closure_request.type", "wrong object type")
    if closure_request.get("protocol_version") != PROTOCOL_VERSION:
        _reject("invalid_protocol_version", "closure_request.protocol_version", "unsupported")
    _validate_domain(closure_request.get("domain"), "closure_request.domain")
    _validate_channel_reference(closure_request.get("channel"), "closure_request.channel")
    if value.get("type") != "closure_snapshot_at_request":
        _reject("invalid_request_snapshot", "snapshot_at_request.type", "wrong object type")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        _reject("invalid_protocol_version", "snapshot_at_request.protocol_version", "unsupported")
    expected_links = {
        "closure_request_hash": closure_request["request_hash"],
        "domain": closure_request["domain"],
        "channel": closure_request["channel"],
        "closure_id": closure_request["closure_id"],
        "channel_snapshot_hash": closure_request["channel_snapshot_hash"],
        "requested_at": closure_request["requested_at"],
        "claim_deadline": closure_request["claim_deadline"],
    }
    mismatches = [
        field for field, expected in expected_links.items() if value.get(field) != expected
    ]
    if mismatches:
        _reject(
            "request_snapshot_link_mismatch",
            "snapshot_at_request",
            ", ".join(sorted(mismatches)),
        )
    if closure_request.get("status") != "requested":
        _reject("invalid_closure_request", "closure_request.status", "expected requested")
    if value.get("channel_status") != "closing":
        _reject("request_snapshot_lifecycle_invalid", "channel_status", "expected closing")
    if value.get("closure_phase") != "claim_window":
        _reject("request_snapshot_phase_invalid", "closure_phase", "expected claim_window")
    if value.get("pre_deadline_refundable_base_units") != "0":
        _reject(
            "pre_deadline_refund_forbidden",
            "pre_deadline_refundable_base_units",
            "must be zero",
        )
    if _time(value.get("claim_deadline"), "snapshot_at_request.claim_deadline") <= _time(
        value.get("requested_at"),
        "snapshot_at_request.requested_at",
    ):
        _reject("close_window_invalid", "snapshot_at_request", "deadline must follow request")
    funded = _amount(value.get("funded_total_base_units"), "request_snapshot.funded")
    activated = _amount(value.get("activated_total_base_units"), "request_snapshot.activated")
    settled = _amount(value.get("settled_total_base_units"), "request_snapshot.settled")
    refunded = _amount(value.get("refunded_total_base_units"), "request_snapshot.refunded")
    vault = _amount(value.get("vault_balance_base_units"), "request_snapshot.vault")
    outstanding = _amount(
        value.get("outstanding_right_base_units"),
        "request_snapshot.outstanding",
    )
    unallocated = _amount(
        value.get("unallocated_capacity_base_units"),
        "request_snapshot.unallocated",
    )
    if funded != vault + settled + refunded:
        _reject("conservation_violation", "snapshot_at_request", "F must equal V + S + R")
    if not 0 <= settled <= activated <= funded - refunded:
        _reject(
            "rights_bounds_violation",
            "snapshot_at_request",
            "requires 0 <= S <= A <= F - R",
        )
    if outstanding != activated - settled:
        _reject("outstanding_right_mismatch", "snapshot_at_request", "must equal A - S")
    if unallocated != funded - refunded - activated:
        _reject(
            "unallocated_capacity_mismatch",
            "snapshot_at_request",
            "must equal F - R - A",
        )
    sequence = value.get("latest_activated_sequence")
    if type(sequence) is not int or sequence < 0:
        _reject(
            "invalid_activated_sequence",
            "snapshot_at_request.latest_activated_sequence",
            "expected non-negative integer",
        )
    _hash(
        value.get("latest_activated_voucher_hash"),
        "snapshot_at_request.latest_activated_voucher_hash",
    )
    if (sequence == 0) != (activated == 0):
        _reject(
            "activation_state_inconsistent",
            "snapshot_at_request",
            "sequence and A must both be zero or both non-zero",
        )
    return funded, activated, settled, refunded


def activation_is_eligible(*, now: datetime, claim_deadline: str) -> bool:
    """Return the exclusive-deadline eligibility decision."""

    return _utc(now) < _time(claim_deadline, "claim_deadline")


def request_close(
    channel: Mapping[str, Any],
    *,
    closure_id: str,
    idempotency_key: str,
    now: datetime,
    claim_deadline: datetime,
) -> ClosureArtifacts:
    """Create a deterministic close request and immutable request snapshot."""

    projection = validate_channel(channel)
    if channel["status"] != "active":
        _reject("close_lifecycle_forbidden", "channel.status", "close requires active")
    requested_at = _utc(now)
    deadline = _utc(claim_deadline)
    minimum_grace = int(channel["policy"]["minimum_close_grace_seconds"])
    if deadline <= requested_at:
        _reject("claim_deadline_not_future", "claim_deadline", "must follow requested_at")
    if (deadline - requested_at).total_seconds() < minimum_grace:
        _reject("close_grace_too_short", "claim_deadline", "below policy minimum")
    request_unsigned = {
        "type": "channel_closure_request",
        "protocol_version": PROTOCOL_VERSION,
        "domain": _domain(channel),
        "channel": _channel_reference(channel),
        "closure_id": _identifier(closure_id, "closure_id"),
        "idempotency_key": _identifier(idempotency_key, "idempotency_key"),
        "channel_snapshot_hash": _snapshot_hash(channel),
        "requested_at": _format_time(requested_at),
        "claim_deadline": _format_time(deadline),
        "status": "requested",
    }
    request = _with_hash(request_unsigned, "request_hash")
    snapshot_unsigned = _closure_snapshot(
        type_name="closure_snapshot_at_request",
        closure_id=closure_id,
        request_link_field="closure_request_hash",
        request_link_hash=request["request_hash"],
        channel=channel,
        projection=projection,
        channel_snapshot_hash=request["channel_snapshot_hash"],
        latest_sequence=int(channel["latest_activated_sequence"]),
        latest_voucher_hash=str(channel["latest_activated_voucher_hash"]),
        requested_at=request["requested_at"],
        claim_deadline=request["claim_deadline"],
    )
    snapshot = _with_hash(snapshot_unsigned, "request_snapshot_hash")
    return ClosureArtifacts(request=request, snapshot_at_request=snapshot)


def _closure_snapshot(
    *,
    type_name: str,
    closure_id: str,
    request_link_field: str,
    request_link_hash: str,
    channel: Mapping[str, Any],
    projection: AccountingProjection,
    channel_snapshot_hash: str,
    latest_sequence: int,
    latest_voucher_hash: str,
    requested_at: str,
    claim_deadline: str,
) -> dict[str, Any]:
    return {
        "type": type_name,
        "protocol_version": PROTOCOL_VERSION,
        "domain": _domain(channel),
        "channel": _channel_reference(channel),
        "closure_id": closure_id,
        request_link_field: request_link_hash,
        "channel_snapshot_hash": channel_snapshot_hash,
        "funded_total_base_units": str(projection.funded_total_base_units),
        "activated_total_base_units": str(projection.activated_authorized_total_base_units),
        "settled_total_base_units": str(projection.settled_total_base_units),
        "refunded_total_base_units": str(projection.refunded_total_base_units),
        "vault_balance_base_units": str(projection.vault_balance_base_units),
        "outstanding_right_base_units": str(projection.outstanding_right_base_units),
        "unallocated_capacity_base_units": str(projection.unallocated_capacity_base_units),
        "latest_activated_sequence": latest_sequence,
        "latest_activated_voucher_hash": latest_voucher_hash,
        "requested_at": requested_at,
        "claim_deadline": claim_deadline,
        "pre_deadline_refundable_base_units": "0",
        "channel_status": "closing",
        "closure_phase": "claim_window",
    }


def freeze_closure(
    closure_request: Mapping[str, Any],
    snapshot_at_request: Mapping[str, Any],
    channel_at_freeze: Mapping[str, Any],
    *,
    now: datetime,
    operation_states: Sequence[str] = (),
) -> dict[str, Any]:
    """Freeze final activation state at or after the exclusive deadline."""

    requested_funded, requested_activated, requested_settled, requested_refunded = (
        _validate_request_snapshot(closure_request, snapshot_at_request)
    )
    frozen_at = _utc(now)
    deadline = _time(closure_request["claim_deadline"], "claim_deadline")
    if frozen_at < deadline:
        _reject("claim_window_open", "now", "freeze requires now >= claim_deadline")
    projection = validate_channel(channel_at_freeze)
    if channel_at_freeze["status"] != "closing":
        _reject("freeze_lifecycle_forbidden", "channel.status", "freeze requires closing")
    if channel_at_freeze["claim_deadline"] != closure_request["claim_deadline"]:
        _reject("deadline_mismatch", "channel.claim_deadline", "must equal closure request")
    if _domain(channel_at_freeze) != closure_request["domain"]:
        _reject("domain_mismatch", "channel", "domain changed during close")
    if _channel_reference(channel_at_freeze) != closure_request["channel"]:
        _reject("channel_reference_mismatch", "channel", "identity changed during close")
    if projection.funded_total_base_units != requested_funded:
        _reject("funding_changed_during_close", "channel", "F must remain unchanged")
    if projection.refunded_total_base_units != requested_refunded:
        _reject("refund_changed_during_claim_window", "channel", "R must remain unchanged")
    if projection.settled_total_base_units < requested_settled:
        _reject("settled_total_decreased", "channel", "S must remain monotonic")
    if projection.activated_authorized_total_base_units < requested_activated:
        _reject("activated_total_decreased", "channel", "A must remain monotonic")
    requested_sequence = int(snapshot_at_request["latest_activated_sequence"])
    frozen_sequence = int(channel_at_freeze["latest_activated_sequence"])
    requested_voucher_hash = str(snapshot_at_request["latest_activated_voucher_hash"])
    frozen_voucher_hash = str(channel_at_freeze["latest_activated_voucher_hash"])
    if frozen_sequence < requested_sequence:
        _reject("activated_sequence_decreased", "channel", "sequence must remain monotonic")
    activation_increased = projection.activated_authorized_total_base_units > requested_activated
    sequence_advanced = frozen_sequence > requested_sequence
    hash_changed = frozen_voucher_hash != requested_voucher_hash
    if activation_increased and not sequence_advanced:
        _reject(
            "activation_transition_inconsistent",
            "channel.latest_activated_sequence",
            "increased A requires a newer activated voucher",
        )
    if sequence_advanced != hash_changed:
        _reject(
            "activation_transition_inconsistent",
            "channel.latest_activated_voucher_hash",
            "sequence advance and voucher hash change must occur together",
        )
    states = _operation_states(operation_states)
    unsigned = {
        "type": "closure_snapshot_at_freeze",
        "protocol_version": PROTOCOL_VERSION,
        "domain": _domain(channel_at_freeze),
        "channel": _channel_reference(channel_at_freeze),
        "closure_id": closure_request["closure_id"],
        "request_snapshot_hash": snapshot_at_request["request_snapshot_hash"],
        "channel_snapshot_hash": _snapshot_hash(channel_at_freeze),
        "funded_total_base_units": str(projection.funded_total_base_units),
        "activated_total_base_units": str(projection.activated_authorized_total_base_units),
        "settled_total_base_units": str(projection.settled_total_base_units),
        "refunded_total_base_units": str(projection.refunded_total_base_units),
        "vault_balance_base_units": str(projection.vault_balance_base_units),
        "outstanding_right_base_units": str(projection.outstanding_right_base_units),
        "excess_refundable_base_units": str(projection.unallocated_capacity_base_units),
        "latest_activated_sequence": channel_at_freeze["latest_activated_sequence"],
        "latest_activated_voucher_hash": channel_at_freeze["latest_activated_voucher_hash"],
        "claim_deadline": closure_request["claim_deadline"],
        "frozen_at": _format_time(frozen_at),
        "unresolved_operation_count": sum(state in _AMBIGUOUS_STATES for state in states),
        "channel_status": "closing",
        "closure_phase": "ready_to_finalize",
    }
    return _with_hash(unsigned, "freeze_snapshot_hash")


def make_refund_request(
    closure_request: Mapping[str, Any],
    freeze_snapshot: Mapping[str, Any],
    *,
    refund_id: str,
    idempotency_key: str,
    reason: str,
    requested_base_units: int,
    now: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Materialize a refund intent without claiming execution."""

    _closed(
        closure_request,
        field="closure_request",
        required=_CLOSURE_REQUEST_FIELDS,
    )
    _validate_hash(closure_request, "request_hash")
    _validate_freeze_snapshot(freeze_snapshot)
    if freeze_snapshot["request_snapshot_hash"] is None:
        _reject("freeze_snapshot_invalid", "freeze_snapshot", "request link is required")
    if freeze_snapshot["closure_id"] != closure_request["closure_id"]:
        _reject("closure_link_mismatch", "freeze_snapshot.closure_id", "wrong closure")
    if freeze_snapshot["domain"] != closure_request["domain"]:
        _reject("domain_mismatch", "freeze_snapshot.domain", "wrong domain")
    if freeze_snapshot["channel"] != closure_request["channel"]:
        _reject("channel_reference_mismatch", "freeze_snapshot.channel", "wrong channel")
    if reason not in _REFUND_REASONS:
        _reject("invalid_refund_reason", "reason", "unsupported v1 reason")
    if requested_base_units <= 0:
        _reject("amount_must_be_positive", "requested_base_units", "must be positive")
    created = _utc(now)
    expiry = _utc(expires_at)
    if expiry <= created:
        _reject("refund_request_expired", "expires_at", "must follow created_at")
    unsigned = {
        "type": "refund_request",
        "protocol_version": PROTOCOL_VERSION,
        "domain": closure_request["domain"],
        "channel": closure_request["channel"],
        "closure_id": closure_request["closure_id"],
        "refund_id": _identifier(refund_id, "refund_id"),
        "idempotency_key": _identifier(idempotency_key, "idempotency_key"),
        "reason": reason,
        "destination": closure_request["channel"]["sender"],
        "requested_base_units": str(requested_base_units),
        "freeze_snapshot_hash": freeze_snapshot["freeze_snapshot_hash"],
        "created_at": _format_time(created),
        "expires_at": _format_time(expiry),
    }
    return _with_hash(unsigned, "request_hash")


def project_refund(
    refund_request: Mapping[str, Any],
    freeze_snapshot: Mapping[str, Any],
    *,
    now: datetime,
    operation_states: Sequence[str] = (),
) -> dict[str, Any]:
    """Validate a refund against final activation and unresolved-operation gates."""

    _closed(refund_request, field="refund_request", required=_REFUND_REQUEST_FIELDS)
    _validate_hash(refund_request, "request_hash")
    _validate_freeze_snapshot(freeze_snapshot)
    if refund_request["freeze_snapshot_hash"] != freeze_snapshot["freeze_snapshot_hash"]:
        _reject("freeze_snapshot_mismatch", "refund_request", "hash mismatch")
    if refund_request["domain"] != freeze_snapshot["domain"]:
        _reject("domain_mismatch", "refund_request.domain", "wrong domain")
    if refund_request["channel"] != freeze_snapshot["channel"]:
        _reject("channel_reference_mismatch", "refund_request.channel", "wrong channel")
    if refund_request["closure_id"] != freeze_snapshot["closure_id"]:
        _reject("closure_link_mismatch", "refund_request.closure_id", "wrong closure")
    if refund_request["destination"] != freeze_snapshot["channel"]["sender"]:
        _reject("refund_destination_substitution", "refund_request.destination", "must be sender")
    _validate_domain(refund_request["domain"], "refund_request.domain")
    _validate_channel_reference(refund_request["channel"], "refund_request.channel")
    _pubkey(refund_request["destination"], "refund_request.destination")
    current = _utc(now)
    if current < _time(freeze_snapshot["claim_deadline"], "claim_deadline"):
        _reject("claim_window_open", "now", "refund requires now >= claim_deadline")
    if current >= _time(refund_request["expires_at"], "refund_request.expires_at"):
        _reject("refund_request_expired", "now", "request is no longer eligible")
    if current < _time(refund_request["created_at"], "refund_request.created_at"):
        _reject("refund_request_not_started", "now", "precedes created_at")
    states = _operation_states(operation_states)
    ambiguous = tuple(state for state in states if state in _AMBIGUOUS_STATES)
    if int(freeze_snapshot["unresolved_operation_count"]) or ambiguous:
        _reject(
            "unresolved_economic_operation",
            "operation_states",
            "refund is blocked until independent recovery and a fresh snapshot",
        )
    funded = _amount(freeze_snapshot["funded_total_base_units"], "freeze.funded")
    activated = _amount(freeze_snapshot["activated_total_base_units"], "freeze.activated")
    settled = _amount(freeze_snapshot["settled_total_base_units"], "freeze.settled")
    refunded = _amount(freeze_snapshot["refunded_total_base_units"], "freeze.refunded")
    vault = _amount(freeze_snapshot["vault_balance_base_units"], "freeze.vault")
    outstanding = activated - settled
    maximum = funded - refunded - activated
    reason = refund_request["reason"]
    if reason not in _REFUND_REASONS:
        _reject("invalid_refund_reason", "refund_request.reason", "unsupported v1 reason")
    if reason == "final_close" and outstanding != 0:
        _reject("outstanding_right_reserved", "refund_request.reason", "A - S must be zero")
    requested = _amount(
        refund_request["requested_base_units"],
        "refund_request.requested_base_units",
        positive=True,
    )
    if requested > maximum:
        _reject("refund_exceeds_unallocated", "requested_base_units", "would consume A - S")
    if requested > vault:
        _reject("refund_exceeds_vault", "requested_base_units", "exceeds observed vault")
    if reason == "final_close" and requested != vault:
        _reject(
            "final_close_requires_full_vault",
            "requested_base_units",
            "final close must consume the entire remaining vault",
        )
    projection = {
        "type": "refund_projection",
        "protocol_version": PROTOCOL_VERSION,
        "refund_request_hash": refund_request["request_hash"],
        "freeze_snapshot_hash": freeze_snapshot["freeze_snapshot_hash"],
        "reason": reason,
        "funded_total_base_units": str(funded),
        "activated_total_base_units": str(activated),
        "settled_total_base_units": str(settled),
        "refunded_total_before_base_units": str(refunded),
        "refunded_total_after_base_units": str(refunded + requested),
        "vault_balance_before_base_units": str(vault),
        "vault_balance_after_base_units": str(vault - requested),
        "outstanding_right_base_units": str(outstanding),
        "maximum_refundable_base_units": str(maximum),
        "requested_base_units": str(requested),
        "unresolved_operation_count": 0,
        "eligible": True,
        "projected_at": _format_time(current),
    }
    return _with_hash(projection, "projection_hash")


def validate_finalization(
    channel: Mapping[str, Any],
    freeze_snapshot: Mapping[str, Any],
    *,
    now: datetime,
    operation_states: Sequence[str],
) -> None:
    """Fail closed unless a caller-provided snapshot is final-close eligible."""

    _validate_freeze_snapshot(freeze_snapshot)
    projection = validate_channel(channel)
    if channel["status"] != "closing":
        _reject("finalization_lifecycle_forbidden", "channel.status", "requires closing")
    if _utc(now) < _time(channel["claim_deadline"], "channel.claim_deadline"):
        _reject("claim_window_open", "now", "finalization requires deadline")
    if projection.outstanding_right_base_units != 0:
        _reject("outstanding_right_reserved", "channel", "A - S must be zero")
    if projection.vault_balance_base_units != 0:
        _reject("vault_not_empty", "channel", "finalization requires V = 0")
    if freeze_snapshot["channel"] != _channel_reference(channel):
        _reject("channel_reference_mismatch", "freeze_snapshot.channel", "wrong channel")
    if int(freeze_snapshot["unresolved_operation_count"]) != 0:
        _reject(
            "unresolved_economic_operation",
            "freeze_snapshot.unresolved_operation_count",
            "finalization blocked",
        )
    if any(state in _AMBIGUOUS_STATES for state in _operation_states(operation_states)):
        _reject("unresolved_economic_operation", "operation_states", "finalization blocked")


def epoch_transition_eligibility(
    previous_channel: Mapping[str, Any],
    *,
    previous_final_closure_hash: str,
    unresolved_operation_count: int,
    now: datetime,
) -> dict[str, Any]:
    """Return an eligibility decision; never claim that a new epoch was created."""

    projection = validate_channel(previous_channel)
    if previous_channel["status"] != "closed":
        _reject("previous_channel_not_closed", "previous_channel.status", "must be closed")
    if projection.vault_balance_base_units != 0:
        _reject("previous_vault_nonzero", "previous_channel", "V must be zero")
    if projection.outstanding_right_base_units != 0:
        _reject("previous_outstanding_nonzero", "previous_channel", "A - S must be zero")
    if unresolved_operation_count != 0:
        _reject("unresolved_economic_operation", "unresolved_operation_count", "must be zero")
    unsigned = {
        "type": "epoch_transition_eligibility",
        "protocol_version": PROTOCOL_VERSION,
        "domain": _domain(previous_channel),
        "channel_id": previous_channel["channel_id"],
        "channel_account": previous_channel["channel_account"],
        "previous_epoch": previous_channel["epoch"],
        "next_epoch": previous_channel["epoch"] + 1,
        "previous_final_closure_hash": _hash(
            previous_final_closure_hash, "previous_final_closure_hash"
        ),
        "previous_status": "closed",
        "previous_vault_balance_base_units": "0",
        "previous_outstanding_right_base_units": "0",
        "unresolved_operation_count": 0,
        "next_funded_total_base_units": "0",
        "next_activated_total_base_units": "0",
        "next_settled_total_base_units": "0",
        "next_refunded_total_base_units": "0",
        "next_latest_sequence": 0,
        "next_latest_voucher_hash": ZERO_HASH,
        "decision": "epoch_transition_eligible",
        "evaluated_at": _format_time(now),
    }
    return _with_hash(unsigned, "eligibility_hash")


class ClosureRuntime:
    """Durable refund reservation and reconciliation journal."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            try:
                connection.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower():
                    raise
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    closure_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    projection_hash TEXT NOT NULL,
                    projection_json TEXT NOT NULL,
                    freeze_snapshot_hash TEXT NOT NULL,
                    requested_amount INTEGER NOT NULL CHECK (requested_amount > 0),
                    maximum_refundable INTEGER NOT NULL,
                    refunded_before INTEGER NOT NULL,
                    refunded_after INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    commitment_json TEXT,
                    execution_request_id TEXT,
                    execution_commitment_hash TEXT,
                    prepared_message_hash TEXT,
                    executor_id TEXT,
                    expected_signer TEXT,
                    submit_intent_count INTEGER NOT NULL DEFAULT 0 CHECK (submit_intent_count <= 1),
                    technical_receipt_json TEXT,
                    transaction_signature TEXT,
                    reconciled_receipt_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (channel_id, epoch, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS refund_events (
                    refund_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    previous_event_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (refund_id, sequence)
                );
                """
            )

    def register_refund(
        self,
        refund_request: Mapping[str, Any],
        freeze_snapshot: Mapping[str, Any],
        *,
        now: datetime,
        operation_states: Sequence[str] = (),
    ) -> RefundRecord:
        projection = project_refund(
            refund_request,
            freeze_snapshot,
            now=now,
            operation_states=operation_states,
        )
        refund_id = _identifier(refund_request["refund_id"], "refund_id")
        channel = refund_request["channel"]
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM refunds
                WHERE refund_id = ?
                   OR (channel_id = ? AND epoch = ? AND idempotency_key = ?)
                """,
                (
                    refund_id,
                    channel["channel_id"],
                    channel["epoch"],
                    refund_request["idempotency_key"],
                ),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != refund_request["request_hash"]:
                    connection.rollback()
                    _reject(
                        "idempotency_conflict",
                        "idempotency_key",
                        "same scope reused with different canonical bytes",
                    )
                connection.commit()
                return self._record(existing)
            reserved = connection.execute(
                """
                SELECT COALESCE(SUM(requested_amount), 0) AS reserved
                FROM refunds
                WHERE channel_id = ? AND epoch = ? AND closure_id = ?
                  AND state NOT IN (
                    'rejected_before_submission',
                    'failed_before_submission',
                    'explicitly_cancelled_before_authorization',
                    'completed'
                  )
                """,
                (
                    channel["channel_id"],
                    channel["epoch"],
                    refund_request["closure_id"],
                ),
            ).fetchone()["reserved"]
            requested = int(projection["requested_base_units"])
            maximum = int(projection["maximum_refundable_base_units"])
            refunded_before = int(projection["refunded_total_before_base_units"])
            refunded_after = int(projection["refunded_total_after_base_units"])
            completed_high_water = connection.execute(
                """
                SELECT COALESCE(MAX(refunded_after), 0) AS high_water
                FROM refunds
                WHERE channel_id = ? AND epoch = ? AND closure_id = ?
                  AND state = 'completed'
                """,
                (
                    channel["channel_id"],
                    channel["epoch"],
                    refund_request["closure_id"],
                ),
            ).fetchone()["high_water"]
            if refunded_before < int(completed_high_water):
                connection.rollback()
                _reject(
                    "stale_freeze_snapshot",
                    "freeze_snapshot.refunded_total_base_units",
                    "does not incorporate the latest reconciled refund",
                )
            if int(reserved) + requested > maximum:
                connection.rollback()
                _reject(
                    "aggregate_refund_exceeds_unallocated",
                    "requested_base_units",
                    "concurrent reservations exceed final unallocated capacity",
                )
            connection.execute(
                """
                INSERT INTO refunds (
                    refund_id, channel_id, epoch, closure_id, idempotency_key,
                    request_hash, request_json, projection_hash, projection_json,
                    freeze_snapshot_hash, requested_amount, maximum_refundable,
                    refunded_before, refunded_after, state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'validated', ?, ?)
                """,
                (
                    refund_id,
                    channel["channel_id"],
                    channel["epoch"],
                    refund_request["closure_id"],
                    refund_request["idempotency_key"],
                    refund_request["request_hash"],
                    json.dumps(refund_request, sort_keys=True, separators=(",", ":")),
                    projection["projection_hash"],
                    json.dumps(projection, sort_keys=True, separators=(",", ":")),
                    freeze_snapshot["freeze_snapshot_hash"],
                    requested,
                    maximum,
                    refunded_before,
                    refunded_after,
                    timestamp,
                    timestamp,
                ),
            )
            self._event(connection, refund_id, "validated", projection, timestamp)
            connection.commit()
        return self.get(refund_id)

    def commit_execution(
        self,
        refund_id: str,
        commitment: Mapping[str, Any],
        *,
        now: datetime,
    ) -> RefundRecord:
        """Persist exact execution correlation before a submit intent exists."""

        _closed(
            commitment,
            field="execution_commitment",
            required=_EXECUTION_COMMITMENT_FIELDS,
        )
        if commitment["type"] != "refund_execution_commitment":
            _reject("invalid_execution_commitment", "commitment.type", "wrong object type")
        if commitment["protocol_version"] != PROTOCOL_VERSION:
            _reject("invalid_protocol_version", "commitment.protocol_version", "unsupported")
        for field in (
            "refund_request_hash",
            "refund_projection_hash",
            "execution_commitment_hash",
            "prepared_message_hash",
        ):
            _hash(commitment[field], f"commitment.{field}")
        for field in ("execution_request_id", "executor_id"):
            _identifier(commitment[field], f"commitment.{field}")
        _pubkey(commitment["expected_signer"], "commitment.expected_signer")
        expires_at = _time(commitment["expires_at"], "commitment.expires_at")
        if _utc(now) >= expires_at:
            _reject("execution_commitment_expired", "commitment.expires_at", "expired")
        timestamp = _format_time(now)
        serialized = json.dumps(commitment, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if row["state"] == "execution_committed":
                if row["commitment_json"] != serialized:
                    connection.rollback()
                    _reject(
                        "execution_commitment_conflict",
                        "commitment",
                        "different exact bytes already persisted",
                    )
                connection.commit()
                return self._record(row)
            if row["state"] != "validated":
                connection.rollback()
                _reject("commitment_state_invalid", "refund.state", str(row["state"]))
            if commitment["refund_request_hash"] != row["request_hash"]:
                connection.rollback()
                _reject("execution_commitment_mismatch", "commitment", "request hash mismatch")
            if commitment["refund_projection_hash"] != row["projection_hash"]:
                connection.rollback()
                _reject(
                    "execution_commitment_mismatch",
                    "commitment",
                    "projection hash mismatch",
                )
            connection.execute(
                """
                UPDATE refunds
                SET state = 'execution_committed', commitment_json = ?,
                    execution_request_id = ?, execution_commitment_hash = ?,
                    prepared_message_hash = ?, executor_id = ?,
                    expected_signer = ?, updated_at = ?
                WHERE refund_id = ?
                """,
                (
                    serialized,
                    commitment["execution_request_id"],
                    commitment["execution_commitment_hash"],
                    commitment["prepared_message_hash"],
                    commitment["executor_id"],
                    commitment["expected_signer"],
                    timestamp,
                    refund_id,
                ),
            )
            self._event(
                connection,
                refund_id,
                "execution_committed",
                commitment,
                timestamp,
            )
            connection.commit()
        return self.get(refund_id)

    def record_submit_intent(self, refund_id: str, *, now: datetime) -> RefundRecord:
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if row["state"] in {"submitted", "needs_recovery", "reconciling", "completed"}:
                connection.commit()
                return self._record(row)
            if row["state"] != "execution_committed":
                connection.rollback()
                _reject("submit_state_invalid", "refund.state", str(row["state"]))
            connection.execute(
                """
                UPDATE refunds
                SET state = 'submitted', submit_intent_count = 1, updated_at = ?
                WHERE refund_id = ?
                """,
                (timestamp, refund_id),
            )
            self._event(
                connection,
                refund_id,
                "submitted",
                {"submit_intent_persisted": True},
                timestamp,
            )
            connection.commit()
        return self.get(refund_id)

    def record_technical_receipt(
        self,
        refund_id: str,
        receipt: Mapping[str, Any],
        *,
        now: datetime,
    ) -> RefundRecord:
        _closed(
            receipt,
            field="technical_receipt",
            required=_TECHNICAL_RECEIPT_REQUIRED,
            allowed=_TECHNICAL_RECEIPT_FIELDS,
        )
        _validate_hash(receipt, "receipt_hash")
        if receipt.get("type") != "technical_refund_receipt":
            _reject("invalid_technical_receipt", "receipt.type", "wrong object type")
        if receipt.get("protocol_version") != PROTOCOL_VERSION:
            _reject("invalid_protocol_version", "receipt.protocol_version", "unsupported")
        _identifier(receipt["refund_id"], "receipt.refund_id")
        _identifier(receipt["execution_request_id"], "receipt.execution_request_id")
        _hash(receipt["refund_request_hash"], "receipt.refund_request_hash")
        _hash(receipt["execution_commitment_hash"], "receipt.execution_commitment_hash")
        _time(receipt["observed_at"], "receipt.observed_at")
        if not isinstance(receipt["technical_status"], str) or not receipt["technical_status"]:
            _reject("invalid_technical_status", "receipt.technical_status", "required")
        timestamp = _format_time(now)
        serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if row["technical_receipt_json"] is not None:
                if row["technical_receipt_json"] != serialized:
                    connection.rollback()
                    _reject(
                        "technical_receipt_conflict",
                        "receipt",
                        "a different technical result is already persisted",
                    )
                connection.commit()
                return self._record(row)
            if row["state"] != "submitted":
                connection.rollback()
                _reject("technical_receipt_state_invalid", "refund.state", str(row["state"]))
            if int(row["submit_intent_count"]) != 1:
                connection.rollback()
                _reject("submit_intent_missing", "refund", "persist intent before receipt")
            if receipt["refund_id"] != refund_id:
                connection.rollback()
                _reject("technical_receipt_mismatch", "receipt.refund_id", "wrong refund")
            if receipt["refund_request_hash"] != row["request_hash"]:
                connection.rollback()
                _reject("technical_receipt_mismatch", "receipt", "request hash mismatch")
            if receipt["execution_request_id"] != row["execution_request_id"]:
                connection.rollback()
                _reject("technical_receipt_mismatch", "receipt", "execution request mismatch")
            if receipt["execution_commitment_hash"] != row["execution_commitment_hash"]:
                connection.rollback()
                _reject("technical_receipt_mismatch", "receipt", "commitment mismatch")
            outcome = receipt["outcome"]
            if outcome not in {"accepted", "rejected", "unknown"}:
                connection.rollback()
                _reject("invalid_technical_outcome", "receipt.outcome", str(outcome))
            signature = receipt.get("transaction_signature")
            signature_status = receipt["signature_status"]
            if signature_status not in {"known", "unknown"}:
                connection.rollback()
                _reject("invalid_signature_status", "receipt.signature_status", signature_status)
            if signature_status == "known" and not signature:
                connection.rollback()
                _reject("technical_signature_missing", "receipt", "known requires signature")
            if signature is not None and (not isinstance(signature, str) or not signature):
                connection.rollback()
                _reject("invalid_transaction_signature", "receipt", "must be non-empty")
            if outcome == "accepted" and signature_status != "known":
                connection.rollback()
                _reject(
                    "accepted_signature_unknown",
                    "receipt.signature_status",
                    "accepted requires a known signature",
                )
            state = (
                "needs_recovery"
                if outcome == "unknown"
                else ("reconciling" if outcome == "accepted" else "needs_review")
            )
            connection.execute(
                """
                UPDATE refunds
                SET state = ?, technical_receipt_json = ?,
                    transaction_signature = ?, updated_at = ?
                WHERE refund_id = ?
                """,
                (
                    state,
                    serialized,
                    signature,
                    timestamp,
                    refund_id,
                ),
            )
            self._event(connection, refund_id, state, receipt, timestamp)
            connection.commit()
        return self.get(refund_id)

    def reconcile(
        self,
        refund_id: str,
        observation: Mapping[str, Any],
        *,
        observation_verifier: RefundObservationVerifier,
        now: datetime,
    ) -> RefundRecord:
        _closed(observation, field="observation", required=_OBSERVATION_FIELDS)
        _validate_hash(observation, "observation_hash")
        if observation.get("type") != "channel_refund_observation":
            _reject("invalid_observation", "observation.type", "wrong object type")
        if observation.get("protocol_version") != PROTOCOL_VERSION:
            _reject("invalid_protocol_version", "observation.protocol_version", "unsupported")
        _identifier(observation["source_id"], "observation.source_id")
        _identifier(observation["refund_id"], "observation.refund_id")
        _validate_domain(observation["domain"], "observation.domain")
        _identifier(observation["channel_id"], "observation.channel_id")
        _pubkey(observation["channel_account"], "observation.channel_account")
        if type(observation["epoch"]) is not int or observation["epoch"] < 0:
            _reject("invalid_epoch", "observation.epoch", "expected non-negative integer")
        _pubkey(observation["mint"], "observation.mint")
        _pubkey(observation["destination"], "observation.destination")
        _hash(observation["refund_request_hash"], "observation.refund_request_hash")
        _hash(observation["refund_projection_hash"], "observation.refund_projection_hash")
        _time(observation["observed_at"], "observation.observed_at")
        if (
            not isinstance(observation["transaction_signature"], str)
            or not observation["transaction_signature"]
        ):
            _reject(
                "invalid_transaction_signature",
                "observation.transaction_signature",
                "required",
            )
        for field in (
            "funded_total_base_units",
            "activated_total_base_units",
            "settled_total_base_units",
            "refunded_total_before_base_units",
            "refunded_total_after_base_units",
            "vault_balance_before_base_units",
            "vault_balance_after_base_units",
        ):
            _amount(observation[field], f"observation.{field}")
        if observation_verifier.source_id != observation.get("source_id"):
            _reject(
                "observation_verifier_mismatch",
                "observation.source_id",
                "verifier is bound to a different source",
            )
        try:
            verified = observation_verifier.verify(observation)
        except Exception:
            verified = False
        if not verified:
            _reject(
                "observation_unverified",
                "observation.observation_hash",
                "independent source verification failed",
            )
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if row["state"] == "completed":
                connection.commit()
                return self._record(row)
            if row["state"] not in {"reconciling", "needs_recovery"}:
                connection.rollback()
                _reject("reconciliation_state_invalid", "refund.state", str(row["state"]))
            request = json.loads(row["request_json"])
            projection = json.loads(row["projection_json"])
            completed_high_water_row = connection.execute(
                """
                SELECT MAX(refunded_after) AS high_water
                FROM refunds
                WHERE channel_id = ? AND epoch = ? AND closure_id = ?
                  AND state = 'completed' AND refund_id <> ?
                """,
                (
                    row["channel_id"],
                    row["epoch"],
                    row["closure_id"],
                    refund_id,
                ),
            ).fetchone()
            completed_high_water = completed_high_water_row["high_water"]
            projected_before = int(projection["refunded_total_before_base_units"])
            if completed_high_water is not None and projected_before < int(completed_high_water):
                connection.execute(
                    "UPDATE refunds SET state = 'needs_review', updated_at = ? WHERE refund_id = ?",
                    (timestamp, refund_id),
                )
                self._event(
                    connection,
                    refund_id,
                    "needs_review",
                    {
                        "reason": "overlapping_refund_interval",
                        "projected_refunded_before": projected_before,
                        "reconciled_refunded_high_water": int(completed_high_water),
                    },
                    timestamp,
                )
                connection.commit()
                _reject(
                    "overlapping_refund_interval",
                    "projection.refunded_total_before_base_units",
                    "a reconciled refund already advanced R beyond this projection",
                )
            expected = {
                "domain": request["domain"],
                "channel_id": request["channel"]["channel_id"],
                "channel_account": request["channel"]["channel_account"],
                "epoch": request["channel"]["epoch"],
                "mint": request["channel"]["mint"],
                "destination": request["destination"],
                "refund_id": refund_id,
                "refund_request_hash": row["request_hash"],
                "refund_projection_hash": row["projection_hash"],
                "funded_total_base_units": projection["funded_total_base_units"],
                "refunded_total_before_base_units": projection["refunded_total_before_base_units"],
                "refunded_total_after_base_units": projection["refunded_total_after_base_units"],
                "vault_balance_before_base_units": projection["vault_balance_before_base_units"],
                "vault_balance_after_base_units": projection["vault_balance_after_base_units"],
                "activated_total_base_units": projection["activated_total_base_units"],
                "settled_total_base_units": projection["settled_total_base_units"],
            }
            mismatches = [key for key, value in expected.items() if observation.get(key) != value]
            if mismatches:
                connection.execute(
                    "UPDATE refunds SET state = 'needs_review', updated_at = ? WHERE refund_id = ?",
                    (timestamp, refund_id),
                )
                self._event(
                    connection,
                    refund_id,
                    "needs_review",
                    {"mismatches": sorted(mismatches)},
                    timestamp,
                )
                connection.commit()
                _reject("reconciliation_mismatch", "observation", ", ".join(mismatches))
            if row["transaction_signature"] != observation.get("transaction_signature"):
                connection.rollback()
                _reject("reconciliation_signature_mismatch", "observation", "wrong signature")
            receipt_unsigned = {
                "type": "reconciled_channel_refund",
                "protocol_version": PROTOCOL_VERSION,
                "refund_id": refund_id,
                "refund_request_hash": row["request_hash"],
                "refund_projection_hash": row["projection_hash"],
                "channel_id": expected["channel_id"],
                "channel_account": expected["channel_account"],
                "epoch": expected["epoch"],
                "mint": expected["mint"],
                "destination": expected["destination"],
                "reason": request["reason"],
                "amount_base_units": request["requested_base_units"],
                "activated_total_base_units": expected["activated_total_base_units"],
                "settled_total_base_units": expected["settled_total_base_units"],
                "refunded_total_before_base_units": expected["refunded_total_before_base_units"],
                "refunded_total_after_base_units": expected["refunded_total_after_base_units"],
                "vault_balance_before_base_units": expected["vault_balance_before_base_units"],
                "vault_balance_after_base_units": expected["vault_balance_after_base_units"],
                "transaction_signature": observation["transaction_signature"],
                "observation_hashes": [observation["observation_hash"]],
                "reconciliation_status": "reference_observation_matched",
                "completed_at": timestamp,
            }
            receipt = _with_hash(receipt_unsigned, "receipt_hash")
            connection.execute(
                """
                UPDATE refunds
                SET state = 'completed', reconciled_receipt_json = ?, updated_at = ?
                WHERE refund_id = ?
                """,
                (
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                    timestamp,
                    refund_id,
                ),
            )
            self._event(connection, refund_id, "completed", receipt, timestamp)
            connection.commit()
        return self.get(refund_id)

    def record_recovered_signature(
        self,
        refund_id: str,
        *,
        transaction_signature: str,
        status_response_hash: str,
        now: datetime,
    ) -> RefundRecord:
        """Recover a known signature without creating another submit intent."""

        if not transaction_signature:
            _reject("recovered_signature_missing", "transaction_signature", "required")
        _hash(status_response_hash, "status_response_hash")
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if row["state"] == "reconciling":
                if row["transaction_signature"] != transaction_signature:
                    connection.rollback()
                    _reject(
                        "recovery_signature_conflict",
                        "transaction_signature",
                        "different signature already recovered",
                    )
                connection.commit()
                return self._record(row)
            if row["state"] != "needs_recovery":
                connection.rollback()
                _reject("recovery_state_invalid", "refund.state", str(row["state"]))
            if int(row["submit_intent_count"]) != 1:
                connection.rollback()
                _reject("submit_intent_missing", "refund", "recovery requires prior intent")
            connection.execute(
                """
                UPDATE refunds
                SET state = 'reconciling', transaction_signature = ?, updated_at = ?
                WHERE refund_id = ?
                """,
                (transaction_signature, timestamp, refund_id),
            )
            self._event(
                connection,
                refund_id,
                "reconciling",
                {
                    "recovery": "signature_located",
                    "status_response_hash": status_response_hash,
                    "submit_intent_count": 1,
                    "automatic_second_submission_count": 0,
                },
                timestamp,
            )
            connection.commit()
        return self.get(refund_id)

    def record_provider_divergence(
        self,
        refund_id: str,
        *,
        provider_ids: Sequence[str],
        now: datetime,
    ) -> RefundRecord:
        """Persist independent-provider disagreement as a disputed state."""

        normalized = sorted({_identifier(value, "provider_id") for value in provider_ids})
        if len(normalized) < 2:
            _reject("provider_divergence_unproven", "provider_ids", "at least two required")
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if row["state"] not in {"needs_recovery", "reconciling", "needs_review"}:
                connection.rollback()
                _reject("divergence_state_invalid", "refund.state", str(row["state"]))
            connection.execute(
                "UPDATE refunds SET state = 'disputed', updated_at = ? WHERE refund_id = ?",
                (timestamp, refund_id),
            )
            self._event(
                connection,
                refund_id,
                "disputed",
                {"provider_ids": normalized},
                timestamp,
            )
            connection.commit()
        return self.get(refund_id)

    def release_before_submission(
        self,
        refund_id: str,
        *,
        state: str,
        now: datetime,
    ) -> RefundRecord:
        if state not in _RELEASING_STATES - {"completed"}:
            _reject("invalid_release_state", "state", state)
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, refund_id)
            if int(row["submit_intent_count"]) != 0 or row["state"] != "validated":
                connection.rollback()
                _reject("release_after_submission_forbidden", "refund", "intent already exists")
            connection.execute(
                "UPDATE refunds SET state = ?, updated_at = ? WHERE refund_id = ?",
                (state, timestamp, refund_id),
            )
            self._event(connection, refund_id, state, {"released": True}, timestamp)
            connection.commit()
        return self.get(refund_id)

    def get(self, refund_id: str) -> RefundRecord:
        with closing(self._connect()) as connection:
            row = self._row(connection, refund_id)
        return self._record(row)

    def _row(self, connection: sqlite3.Connection, refund_id: str) -> sqlite3.Row:
        _identifier(refund_id, "refund_id")
        row = connection.execute(
            "SELECT * FROM refunds WHERE refund_id = ?",
            (refund_id,),
        ).fetchone()
        if row is None:
            _reject("refund_not_found", "refund_id", "unknown refund")
        return row

    def _record(self, row: sqlite3.Row) -> RefundRecord:
        return RefundRecord(
            refund_id=row["refund_id"],
            request_hash=row["request_hash"],
            projection_hash=row["projection_hash"],
            state=row["state"],
            submit_intent_count=int(row["submit_intent_count"]),
            transaction_signature=row["transaction_signature"],
            reconciled_receipt=(
                None
                if row["reconciled_receipt_json"] is None
                else json.loads(row["reconciled_receipt_json"])
            ),
        )

    def _event(
        self,
        connection: sqlite3.Connection,
        refund_id: str,
        state: str,
        payload: Mapping[str, Any],
        timestamp: str,
    ) -> None:
        previous = connection.execute(
            """
            SELECT sequence, event_hash FROM refund_events
            WHERE refund_id = ? ORDER BY sequence DESC LIMIT 1
            """,
            (refund_id,),
        ).fetchone()
        sequence = 1 if previous is None else int(previous["sequence"]) + 1
        previous_hash = ZERO_HASH if previous is None else str(previous["event_hash"])
        event = {
            "refund_id": refund_id,
            "sequence": sequence,
            "state": state,
            "payload": dict(payload),
            "previous_event_hash": previous_hash,
            "recorded_at": timestamp,
        }
        event_hash = _canonical_hash(event)
        connection.execute(
            """
            INSERT INTO refund_events (
                refund_id, sequence, state, event_json,
                previous_event_hash, event_hash, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                refund_id,
                sequence,
                state,
                json.dumps(event, sort_keys=True, separators=(",", ":")),
                previous_hash,
                event_hash,
                timestamp,
            ),
        )
