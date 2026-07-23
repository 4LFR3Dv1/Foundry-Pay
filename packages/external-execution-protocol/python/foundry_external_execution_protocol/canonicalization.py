"""Normative domain validation, RFC 8785 canonicalization, and hashing."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

import rfc8785


PROFILE = "foundry-pay-domain-v1"
PROTOCOL_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {character: index for index, character in enumerate(_BASE58_ALPHABET)}
_PLAN_REQUIRED = {
    "protocol_version",
    "normalization_profile",
    "obligation_id",
    "network",
    "asset",
    "amount_base_units",
    "source",
    "destination",
    "expires_at",
}
_PLAN_OPTIONAL = {"reason"}
_COMMITMENT_REQUIRED = {
    "protocol_version",
    "normalization_profile",
    "execution_request_id",
    "executor_id",
    "executor_version",
    "economic_plan_hash",
    "prepared_message_hash",
    "simulation_attestation_hash",
    "signer",
    "constraints",
    "expires_at",
}


class DomainNormalizationError(ValueError):
    """Input is not in the normative domain representation."""


def _reject_floats(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise DomainNormalizationError(f"{path}: floating-point values are forbidden")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_floats(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_floats(child, f"{path}[{index}]")


def _require_closed_keys(
    value: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    path: str,
) -> None:
    optional = optional or set()
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        raise DomainNormalizationError(f"{path}: missing keys: {sorted(missing)}")
    if unknown:
        raise DomainNormalizationError(f"{path}: unknown keys: {sorted(unknown)}")
    nulls = sorted(key for key, child in value.items() if child is None)
    if nulls:
        raise DomainNormalizationError(f"{path}: null is forbidden: {nulls}")


def _require_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DomainNormalizationError(f"{path}: invalid identifier")
    return value


def _require_timestamp(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise DomainNormalizationError(f"{path}: expected UTC RFC 3339 with second precision")
    return value


def _decode_base58(value: str) -> bytes:
    number = 0
    try:
        for character in value:
            number = number * 58 + _BASE58_INDEX[character]
    except KeyError as error:
        raise DomainNormalizationError("invalid base58 character") from error
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + payload


def _require_solana_pubkey(value: Any, path: str) -> str:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        raise DomainNormalizationError(f"{path}: invalid Solana public key length")
    decoded = _decode_base58(value)
    if len(decoded) != 32:
        raise DomainNormalizationError(f"{path}: Solana public key must decode to 32 bytes")
    return value


def _require_hash(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise DomainNormalizationError(f"{path}: invalid sha256 digest")
    return value


def normalize_economic_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return the exact canonical domain representation."""

    if not isinstance(plan, Mapping):
        raise DomainNormalizationError("$: economic plan must be an object")
    _reject_floats(plan)
    _require_closed_keys(
        plan,
        required=_PLAN_REQUIRED,
        optional=_PLAN_OPTIONAL,
        path="$",
    )
    if plan["protocol_version"] != PROTOCOL_VERSION:
        raise DomainNormalizationError("$.protocol_version: unsupported version")
    if plan["normalization_profile"] != PROFILE:
        raise DomainNormalizationError("$.normalization_profile: unsupported profile")
    _require_identifier(plan["obligation_id"], "$.obligation_id")
    if plan["network"] != "solana-devnet":
        raise DomainNormalizationError("$.network: unsupported network")
    amount = plan["amount_base_units"]
    if not isinstance(amount, str) or not _AMOUNT.fullmatch(amount):
        raise DomainNormalizationError("$.amount_base_units: non-canonical amount")
    if int(amount) <= 0:
        raise DomainNormalizationError("$.amount_base_units: must be greater than zero")
    _require_solana_pubkey(plan["source"], "$.source")
    _require_solana_pubkey(plan["destination"], "$.destination")
    _require_timestamp(plan["expires_at"], "$.expires_at")

    asset = plan["asset"]
    if not isinstance(asset, Mapping):
        raise DomainNormalizationError("$.asset: must be an object")
    _require_closed_keys(
        asset,
        required={"kind", "mint", "decimals"},
        path="$.asset",
    )
    if asset["kind"] != "spl-token":
        raise DomainNormalizationError("$.asset.kind: unsupported asset kind")
    _require_solana_pubkey(asset["mint"], "$.asset.mint")
    decimals = asset["decimals"]
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 18:
        raise DomainNormalizationError("$.asset.decimals: expected integer from 0 to 18")

    if "reason" in plan:
        reason = plan["reason"]
        if not isinstance(reason, str) or not 1 <= len(reason) <= 256:
            raise DomainNormalizationError("$.reason: expected 1 to 256 characters")

    return {
        key: dict(value) if isinstance(value, Mapping) else value for key, value in plan.items()
    }


def canonicalize(value: Any) -> bytes:
    """Return RFC 8785 canonical JSON bytes after rejecting floats."""

    _reject_floats(value)
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, rfc8785.FloatDomainError) as error:
        raise DomainNormalizationError(str(error)) from error


def sha256_digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def economic_plan_hash(plan: Mapping[str, Any]) -> str:
    return sha256_digest(canonicalize(normalize_economic_plan(plan)))


def prepared_message_hash(serialized_message: bytes) -> str:
    if not isinstance(serialized_message, bytes) or not serialized_message:
        raise DomainNormalizationError("serialized message must be non-empty bytes")
    return sha256_digest(serialized_message)


def simulation_attestation_hash(attestation: Mapping[str, Any]) -> str:
    if not isinstance(attestation, Mapping):
        raise DomainNormalizationError("simulation attestation must be an object")
    return sha256_digest(canonicalize(attestation))


def execution_commitment_hash(commitment: Mapping[str, Any]) -> str:
    if not isinstance(commitment, Mapping):
        raise DomainNormalizationError("execution commitment must be an object")
    _reject_floats(commitment)
    _require_closed_keys(commitment, required=_COMMITMENT_REQUIRED, path="$")
    if commitment["protocol_version"] != PROTOCOL_VERSION:
        raise DomainNormalizationError("$.protocol_version: unsupported version")
    if commitment["normalization_profile"] != PROFILE:
        raise DomainNormalizationError("$.normalization_profile: unsupported profile")
    _require_identifier(commitment["execution_request_id"], "$.execution_request_id")
    _require_identifier(commitment["executor_id"], "$.executor_id")
    if not isinstance(commitment["executor_version"], str) or not commitment["executor_version"]:
        raise DomainNormalizationError("$.executor_version: required")
    _require_hash(commitment["economic_plan_hash"], "$.economic_plan_hash")
    _require_hash(commitment["prepared_message_hash"], "$.prepared_message_hash")
    _require_hash(
        commitment["simulation_attestation_hash"],
        "$.simulation_attestation_hash",
    )
    _require_solana_pubkey(commitment["signer"], "$.signer")
    if not isinstance(commitment["constraints"], Mapping):
        raise DomainNormalizationError("$.constraints: must be an object")
    _require_timestamp(commitment["expires_at"], "$.expires_at")
    return sha256_digest(canonicalize(commitment))
