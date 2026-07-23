"""Immutable source observations and deterministic reconciliation consensus."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, Mapping

from foundry_external_execution_protocol import canonicalize, sha256_digest

PROTOCOL_VERSION = "1.0.0"
PROFILE = "foundry-pay-domain-v1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_OBSERVATION_FIELDS = {
    "type",
    "protocol_version",
    "normalization_profile",
    "source_id",
    "source_class",
    "source_kind",
    "provider_id",
    "trust_domain_id",
    "endpoint_identity_hash",
    "parser_id",
    "queried_at",
    "signature",
    "network",
    "slot",
    "confirmation_status",
    "transaction_error",
    "source_account",
    "destination_account",
    "source_account_before",
    "source_account_after",
    "destination_account_before",
    "destination_account_after",
    "observed_amount_base_units",
    "raw_response_hash",
}
_EXPECTED_FIELDS = {
    "execution_request_id",
    "obligation_id",
    "network",
    "signature",
    "source_account",
    "destination_account",
    "amount_base_units",
}

SourceClass = Literal["L1", "L2", "L3"]
SourceKind = Literal["rpc", "archival_rpc", "indexer", "explorer", "validator"]


class ReconciliationInvalid(ValueError):
    """Observation, source authority, or expected settlement is invalid."""


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    source_class: SourceClass
    source_kind: SourceKind
    provider_id: str
    trust_domain_id: str
    endpoint_identity_hash: str
    parser_id: str

    def __post_init__(self) -> None:
        for field in ("source_id", "provider_id", "trust_domain_id", "parser_id"):
            _identifier(getattr(self, field), f"$source.{field}")
        if self.source_class not in {"L1", "L2", "L3"}:
            raise ReconciliationInvalid("$source.source_class: unsupported class")
        if self.source_kind not in {
            "rpc",
            "archival_rpc",
            "indexer",
            "explorer",
            "validator",
        }:
            raise ReconciliationInvalid("$source.source_kind: unsupported kind")
        _digest(self.endpoint_identity_hash, "$source.endpoint_identity_hash")
        if self.source_class == "L3" and self.source_kind not in {
            "archival_rpc",
            "indexer",
            "explorer",
            "validator",
        }:
            raise ReconciliationInvalid("L3 requires a distinct indexed or validating pipeline")


class SourceRegistry:
    """Authoritative source metadata; observations cannot self-assert diversity."""

    def __init__(self, descriptors: list[SourceDescriptor]):
        self._sources: dict[str, SourceDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.source_id in self._sources:
                raise ReconciliationInvalid("duplicate source_id in registry")
            self._sources[descriptor.source_id] = descriptor

    def require(self, observation: Mapping[str, Any]) -> SourceDescriptor:
        source_id = observation.get("source_id")
        descriptor = self._sources.get(source_id) if isinstance(source_id, str) else None
        if descriptor is None:
            raise ReconciliationInvalid("observation source is not registered")
        for field, expected in asdict(descriptor).items():
            if observation.get(field) != expected:
                raise ReconciliationInvalid(
                    f"observation source metadata does not match registry: {field}"
                )
        return descriptor


def endpoint_identity_hash(endpoint: str) -> str:
    """Hash a normalized endpoint identity without persisting credentials."""

    if not isinstance(endpoint, str) or not endpoint:
        raise ReconciliationInvalid("endpoint identity must be a non-empty string")
    normalized = endpoint.strip().rstrip("/").lower()
    if "?" in normalized or "@" in normalized:
        raise ReconciliationInvalid("credential-bearing endpoint identities are forbidden")
    return sha256_digest(normalized.encode("utf-8"))


def raw_response_hash(payload: bytes) -> str:
    if not isinstance(payload, bytes) or not payload:
        raise ReconciliationInvalid("raw response must be non-empty bytes")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def normalize_observation(value: Mapping[str, Any]) -> dict[str, Any]:
    observation = _closed(value, _OBSERVATION_FIELDS, "$observation")
    if observation["type"] != "source_observation":
        raise ReconciliationInvalid("$observation.type: unsupported type")
    if observation["protocol_version"] != PROTOCOL_VERSION:
        raise ReconciliationInvalid("$observation.protocol_version: unsupported version")
    if observation["normalization_profile"] != PROFILE:
        raise ReconciliationInvalid("$observation.normalization_profile: unsupported profile")
    for field in ("source_id", "provider_id", "trust_domain_id", "parser_id"):
        _identifier(observation[field], f"$observation.{field}")
    if observation["source_class"] not in {"L1", "L2", "L3"}:
        raise ReconciliationInvalid("$observation.source_class: unsupported class")
    if observation["source_kind"] not in {
        "rpc",
        "archival_rpc",
        "indexer",
        "explorer",
        "validator",
    }:
        raise ReconciliationInvalid("$observation.source_kind: unsupported kind")
    for field in ("endpoint_identity_hash", "raw_response_hash"):
        _digest(observation[field], f"$observation.{field}")
    _timestamp(observation["queried_at"], "$observation.queried_at")
    if (
        not isinstance(observation["signature"], str)
        or not 64 <= len(observation["signature"]) <= 128
    ):
        raise ReconciliationInvalid("$observation.signature: invalid signature")
    if observation["network"] != "solana:devnet":
        raise ReconciliationInvalid("$observation.network: unsupported network")
    slot = observation["slot"]
    if not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot <= MAX_SAFE_INTEGER:
        raise ReconciliationInvalid("$observation.slot: unsafe unsigned integer")
    if observation["confirmation_status"] not in {"confirmed", "finalized"}:
        raise ReconciliationInvalid("$observation.confirmation_status: unsupported status")
    error = observation["transaction_error"]
    if error != "none":
        _digest(error, "$observation.transaction_error")
    for field in ("source_account", "destination_account"):
        _solana_address(observation[field], f"$observation.{field}")
    amounts = {}
    for field in (
        "source_account_before",
        "source_account_after",
        "destination_account_before",
        "destination_account_after",
        "observed_amount_base_units",
    ):
        amounts[field] = _amount(observation[field], f"$observation.{field}")
    source_delta = amounts["source_account_before"] - amounts["source_account_after"]
    destination_delta = amounts["destination_account_after"] - amounts["destination_account_before"]
    if source_delta < 0 or destination_delta < 0:
        raise ReconciliationInvalid("observation balance directions are invalid")
    if source_delta != destination_delta or source_delta != amounts["observed_amount_base_units"]:
        raise ReconciliationInvalid("observation balance deltas do not match observed amount")
    return dict(observation)


def observation_hash(value: Mapping[str, Any]) -> str:
    return sha256_digest(canonicalize(normalize_observation(value)))


def aggregate_reconciliation(
    expected: Mapping[str, Any],
    observations: list[Mapping[str, Any]],
    registry: SourceRegistry,
    *,
    unavailable_source_ids: list[str] | None = None,
) -> dict[str, Any]:
    settlement = _normalize_expected(expected)
    if not observations:
        return _aggregate_result(
            settlement,
            [],
            execution_status="unknown",
            reconciliation_status="pending",
            independent_verification="pending",
            consensus="pending",
            unavailable=unavailable_source_ids or [],
        )

    seen_sources: set[str] = set()
    seen_hashes: set[str] = set()
    evaluated: list[dict[str, Any]] = []
    normalized_observations: list[dict[str, Any]] = []
    descriptors: dict[str, SourceDescriptor] = {}
    for supplied in observations:
        observation = normalize_observation(supplied)
        descriptor = registry.require(observation)
        digest = observation_hash(observation)
        if descriptor.source_id in seen_sources or digest in seen_hashes:
            raise ReconciliationInvalid("duplicate observation source or hash")
        seen_sources.add(descriptor.source_id)
        seen_hashes.add(digest)
        normalized_observations.append(observation)
        descriptors[descriptor.source_id] = descriptor
        disagreements = _disagreements(settlement, observation)
        evaluated.append(
            {
                "source_id": descriptor.source_id,
                "source_class": descriptor.source_class,
                "observation_hash": digest,
                "result": "matched" if not disagreements else "disagreed",
                "disagreements": disagreements,
            }
        )

    disputed = any(item["result"] == "disagreed" for item in evaluated)
    matched = [item for item in evaluated if item["result"] == "matched"]
    matched_l1 = [item for item in matched if item["source_class"] == "L1"]
    observed_statuses = [
        observation["confirmation_status"]
        for observation, item in zip(normalized_observations, evaluated, strict=True)
        if item["result"] == "matched"
    ]
    if "finalized" in observed_statuses:
        execution_status = "finalized"
    elif observed_statuses:
        execution_status = "confirmed"
    else:
        execution_status = "unknown"

    if disputed:
        reconciliation_status = "reconciliation_disputed"
        independent = "disputed"
        consensus = "disputed"
    elif not matched_l1:
        reconciliation_status = "pending"
        independent = "pending"
        consensus = "pending"
    else:
        reconciliation_status = "l1_verified"
        consensus = "approved"
        l1_descriptors = [descriptors[item["source_id"]] for item in matched_l1]
        qualifying_l2 = [
            item
            for item in matched
            if item["source_class"] == "L2"
            and _diverse_from_l1(descriptors[item["source_id"]], l1_descriptors)
        ]
        qualifying_l3 = [
            item
            for item in matched
            if item["source_class"] == "L3"
            and _diverse_from_l1(descriptors[item["source_id"]], l1_descriptors)
        ]
        if qualifying_l3:
            independent = "l3_verified"
        elif qualifying_l2:
            independent = "l2_verified"
        else:
            independent = "pending"

    return _aggregate_result(
        settlement,
        evaluated,
        execution_status=execution_status,
        reconciliation_status=reconciliation_status,
        independent_verification=independent,
        consensus=consensus,
        unavailable=unavailable_source_ids or [],
    )


def _diverse_from_l1(
    candidate: SourceDescriptor,
    baselines: list[SourceDescriptor],
) -> bool:
    return all(
        candidate.provider_id != baseline.provider_id
        and candidate.trust_domain_id != baseline.trust_domain_id
        and candidate.endpoint_identity_hash != baseline.endpoint_identity_hash
        for baseline in baselines
    )


def _disagreements(
    expected: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> list[str]:
    compared = {
        "network": "network",
        "signature": "signature",
        "source_account": "source_account",
        "destination_account": "destination_account",
        "amount_base_units": "observed_amount_base_units",
    }
    differences = [
        expected_field
        for expected_field, observation_field in compared.items()
        if expected[expected_field] != observation[observation_field]
    ]
    if observation["transaction_error"] != "none":
        differences.append("transaction_error")
    return differences


def _aggregate_result(
    expected: Mapping[str, Any],
    observations: list[Mapping[str, Any]],
    *,
    execution_status: str,
    reconciliation_status: str,
    independent_verification: str,
    consensus: str,
    unavailable: list[str],
) -> dict[str, Any]:
    return {
        "type": "reconciliation_result",
        "protocol_version": PROTOCOL_VERSION,
        "execution_request_id": expected["execution_request_id"],
        "obligation_id": expected["obligation_id"],
        "expected_amount_base_units": expected["amount_base_units"],
        "execution_status": execution_status,
        "reconciliation_status": reconciliation_status,
        "independent_verification": independent_verification,
        "consensus": consensus,
        "observations": list(observations),
        "unavailable_source_ids": list(unavailable),
    }


def _normalize_expected(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = _closed(value, _EXPECTED_FIELDS, "$expected")
    _identifier(expected["execution_request_id"], "$expected.execution_request_id")
    _identifier(expected["obligation_id"], "$expected.obligation_id")
    if expected["network"] != "solana:devnet":
        raise ReconciliationInvalid("$expected.network: unsupported network")
    if not isinstance(expected["signature"], str) or not expected["signature"]:
        raise ReconciliationInvalid("$expected.signature: required")
    _solana_address(expected["source_account"], "$expected.source_account")
    _solana_address(expected["destination_account"], "$expected.destination_account")
    _amount(expected["amount_base_units"], "$expected.amount_base_units")
    return dict(expected)


def _closed(
    value: Mapping[str, Any],
    fields: set[str],
    path: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReconciliationInvalid(f"{path}: expected object")
    keys = set(value)
    if keys != fields:
        raise ReconciliationInvalid(
            f"{path}: invalid fields; missing={sorted(fields - keys)}, "
            f"unknown={sorted(keys - fields)}"
        )
    if any(child is None for child in value.values()):
        raise ReconciliationInvalid(f"{path}: null is forbidden")
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ReconciliationInvalid(f"{path}: invalid identifier")
    return value


def _digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ReconciliationInvalid(f"{path}: invalid sha256 digest")
    return value


def _timestamp(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ReconciliationInvalid(f"{path}: invalid UTC timestamp")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ReconciliationInvalid(f"{path}: invalid UTC calendar timestamp") from error
    return value


def _amount(value: Any, path: str) -> int:
    if not isinstance(value, str) or not _AMOUNT.fullmatch(value):
        raise ReconciliationInvalid(f"{path}: invalid base-unit amount")
    return int(value)


def _solana_address(value: Any, path: str) -> str:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        raise ReconciliationInvalid(f"{path}: invalid Solana address")
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    try:
        for character in value:
            number = number * 58 + alphabet.index(character)
    except ValueError as error:
        raise ReconciliationInvalid(f"{path}: invalid base58") from error
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    payload = b"\x00" * (len(value) - len(value.lstrip("1"))) + payload
    if len(payload) != 32:
        raise ReconciliationInvalid(f"{path}: address must decode to 32 bytes")
    return value
