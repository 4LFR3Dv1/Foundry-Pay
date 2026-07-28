"""Closed draft channel capability contracts for the offline fake adapter.

These contracts describe an executor-shaped transport-independent boundary.
They do not grant economic authority and do not describe Solana instructions.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NoReturn

from .canonical import (
    canonical_json_bytes,
    sha256_canonical_json,
    sha256_raw_bytes,
    validate_amount_text,
    validate_timestamp_text,
)


PROTOCOL_VERSION = "0.1.0-draft"
CAPABILITY_ID = "foundry.channels.fixture.operation.v0"
EXECUTOR_ID = "foundry.channels.fixture-adapter"
LIMITATION = "Fixture environment. No real assets. No production custody or security claim."
OPERATION_STATES = frozenset(
    {
        "draft",
        "prepared",
        "authorized",
        "submitted",
        "needs_recovery",
        "confirmed",
        "reconciled",
        "needs_review",
        "disputed",
        "failed_definitive",
    }
)
OPERATION_KINDS = frozenset({"open", "top_up", "settle", "close", "refund"})

_REQUEST_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "capability_id",
        "request_id",
        "operation_id",
        "idempotency_key",
        "operation_kind",
        "channel_id",
        "epoch",
        "sender",
        "recipient",
        "destination_wallet",
        "mint",
        "amount_base_units",
        "authorization_commitment",
        "expires_at",
    }
)
_AUTHORIZATION_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "capability_id",
        "request_id",
        "operation_id",
        "prepared_material_hash",
        "operation_commitment",
        "authorization_id",
        "expires_at",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "capability_id",
        "request_id",
        "operation_id",
        "technical_receipt_hash",
        "provider_ids",
        "economic_outcome",
        "observed_at",
    }
)
_RECOVERY_REQUEST_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "capability_id",
        "request_id",
        "operation_id",
        "recovery_id",
        "requested_at",
    }
)


class CapabilityContractError(ValueError):
    """Stable fail-closed capability error."""

    def __init__(self, code: str, stage: str, detail: str) -> None:
        self.code = code
        self.stage = stage
        self.detail = detail
        super().__init__(f"{stage}:{code}: {detail}")


def _reject(code: str, stage: str, detail: str) -> NoReturn:
    raise CapabilityContractError(code, stage, detail)


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], path: str) -> None:
    if not isinstance(value, Mapping):
        _reject("invalid_object", "schema", f"{path} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        _reject(
            "closed_object_violation",
            "schema",
            f"{path} missing={missing!r} unknown={unknown!r}",
        )


def _identifier(value: Any, path: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
            for character in value
        )
    ):
        _reject("invalid_identifier", "schema", path)
    return value


def _hash(value: Any, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        _reject("invalid_hash", "schema", path)
    return value


def _version_and_capability(value: Mapping[str, Any]) -> None:
    if value.get("protocol_version") != PROTOCOL_VERSION:
        _reject("unsupported_version", "capability", "no version fallback is permitted")
    if value.get("capability_id") != CAPABILITY_ID:
        _reject("unsupported_capability", "capability", "no capability alias is permitted")


def parse_timestamp(value: str) -> datetime:
    validate_timestamp_text(value, path="$.expires_at")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def validate_operation_request(
    value: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Validate a complete caller-selected economic operation fixture."""

    _exact_fields(value, _REQUEST_FIELDS, "$request")
    _version_and_capability(value)
    if value["type"] != "channel_operation_request":
        _reject("wrong_type", "schema", "request type is not supported")
    for field in (
        "request_id",
        "operation_id",
        "idempotency_key",
        "channel_id",
        "sender",
        "recipient",
        "destination_wallet",
        "mint",
    ):
        _identifier(value[field], f"$.{field}")
    if value["operation_kind"] not in OPERATION_KINDS:
        _reject("unsupported_operation", "schema", "operation kind is not registered")
    if type(value["epoch"]) is not int or value["epoch"] < 0:
        _reject("invalid_epoch", "schema", "epoch must be an unsigned integer")
    validate_amount_text(value["amount_base_units"], path="$.amount_base_units")
    _hash(value["authorization_commitment"], "$.authorization_commitment")
    expiry = parse_timestamp(value["expires_at"])
    normalized_now = now.astimezone(UTC)
    if expiry <= normalized_now:
        _reject("request_expired", "lifecycle", "request has expired")
    return dict(value)


def validate_authorization(
    value: Mapping[str, Any],
    *,
    prepared: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Validate a caller-provided authorization bound to exact fake bytes."""

    _exact_fields(value, _AUTHORIZATION_FIELDS, "$authorization")
    _version_and_capability(value)
    if value["type"] != "channel_operation_authorization":
        _reject("wrong_type", "schema", "authorization type is not supported")
    for field in ("request_id", "operation_id", "authorization_id"):
        _identifier(value[field], f"$.{field}")
    for field in ("prepared_material_hash", "operation_commitment"):
        _hash(value[field], f"$.{field}")
    for field in (
        "request_id",
        "operation_id",
        "prepared_material_hash",
        "operation_commitment",
    ):
        if value[field] != prepared[field]:
            _reject("authorization_mismatch", "authorization", f"{field} differs")
    expiry = parse_timestamp(value["expires_at"])
    if expiry <= now.astimezone(UTC):
        _reject("authorization_expired", "authorization", "authorization has expired")
    if expiry > parse_timestamp(str(prepared["expires_at"])):
        _reject("authorization_outlives_preparation", "authorization", "expiry is too late")
    return dict(value)


def validate_observation(
    value: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate an independent fixture observation without trusting its outcome."""

    _exact_fields(value, _OBSERVATION_FIELDS, "$observation")
    _version_and_capability(value)
    if value["type"] != "channel_economic_observation":
        _reject("wrong_type", "schema", "observation type is not supported")
    for field in ("request_id", "operation_id"):
        _identifier(value[field], f"$.{field}")
        if value[field] != receipt[field]:
            _reject("observation_mismatch", "reconciliation", f"{field} differs")
    _hash(value["technical_receipt_hash"], "$.technical_receipt_hash")
    if value["technical_receipt_hash"] != receipt["technical_receipt_hash"]:
        _reject("receipt_mismatch", "reconciliation", "technical receipt differs")
    providers = value["provider_ids"]
    if (
        not isinstance(providers, list)
        or len(providers) == 0
        or providers != sorted(set(providers))
    ):
        _reject("invalid_providers", "reconciliation", "providers must be sorted and unique")
    try:
        for provider in providers:
            _identifier(provider, "$.provider_ids[]")
    except CapabilityContractError as error:
        _reject(
            "invalid_providers",
            "reconciliation",
            f"provider identifier is invalid: {error.detail}",
        )
    if value["economic_outcome"] not in {"matched", "mismatch", "divergent"}:
        _reject("invalid_outcome", "reconciliation", "unknown economic outcome")
    validate_timestamp_text(value["observed_at"], path="$.observed_at")
    return dict(value)


def validate_recovery_request(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a closed recovery query that grants no resubmission authority."""

    _exact_fields(value, _RECOVERY_REQUEST_FIELDS, "$recovery")
    _version_and_capability(value)
    if value["type"] != "channel_recovery_request":
        _reject("wrong_type", "schema", "recovery request type is not supported")
    for field in ("request_id", "operation_id", "recovery_id"):
        _identifier(value[field], f"$.{field}")
    validate_timestamp_text(value["requested_at"], path="$.requested_at")
    return dict(value)


def capability_manifest() -> dict[str, Any]:
    """Return the immutable draft fixture capability description."""

    return {
        "type": "channel_capability_manifest",
        "protocol_version": PROTOCOL_VERSION,
        "executor_id": EXECUTOR_ID,
        "capabilities": [
            {
                "capability_id": CAPABILITY_ID,
                "actions": ["authorize", "evidence", "prepare", "recover", "status", "submit"],
                "authority": "none",
                "economic_completion": False,
                "solana_compatibility": "not_claimed",
            }
        ],
        "limitation": LIMITATION,
    }


def prepare_operation(request: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    """Materialize deterministic fake bytes from an already validated request."""

    validated = validate_operation_request(request, now=now)
    request_hash = sha256_canonical_json(validated)
    material = b"foundry-channel-fixture-operation-v0\x00" + canonical_json_bytes(validated)
    material_hash = sha256_raw_bytes(material)
    commitment_projection = {
        "type": "channel_execution_commitment",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": validated["request_id"],
        "operation_id": validated["operation_id"],
        "request_hash": request_hash,
        "prepared_material_hash": material_hash,
        "executor_id": EXECUTOR_ID,
        "expected_authority_commitment": validated["authorization_commitment"],
        "expires_at": validated["expires_at"],
    }
    return {
        "type": "prepared_channel_operation",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": validated["request_id"],
        "operation_id": validated["operation_id"],
        "request_hash": request_hash,
        "prepared_material_base64": base64.b64encode(material).decode("ascii"),
        "prepared_material_hash": material_hash,
        "operation_commitment": sha256_canonical_json(commitment_projection),
        "executor_id": EXECUTOR_ID,
        "expires_at": validated["expires_at"],
    }


@dataclass(frozen=True)
class OperationStatus:
    request_id: str
    operation_id: str
    state: str
    submit_intent_count: int
    automatic_resubmission_count: int
    updated_at: str
    technical_receipt: dict[str, Any] | None
    reconciled_result: dict[str, Any] | None

    def __post_init__(self) -> None:
        if self.state not in OPERATION_STATES:
            raise ValueError(f"unknown state: {self.state}")

    def as_contract(self) -> dict[str, Any]:
        return {
            "type": "channel_operation_status",
            "protocol_version": PROTOCOL_VERSION,
            "capability_id": CAPABILITY_ID,
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "state": self.state,
            "submit_intent_count": self.submit_intent_count,
            "automatic_resubmission_count": self.automatic_resubmission_count,
            "updated_at": self.updated_at,
        }
