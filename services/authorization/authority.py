"""Foundry authority for exact-message, single-use execution authorization."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from foundry_external_execution_protocol import (
    canonicalize,
    economic_plan_hash,
    execution_commitment_hash,
    normalize_economic_plan,
    prepared_message_hash,
    sha256_digest,
    simulation_attestation_hash,
)

PROTOCOL_VERSION = "1.0.0"
PROFILE = "foundry-pay-domain-v1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_AUTHORIZATION_TTL_SECONDS = 60
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {character: index for index, character in enumerate(_BASE58_ALPHABET)}
_PREPARED_FIELDS = {
    "type",
    "protocol_version",
    "execution_request_id",
    "executor_id",
    "executor_version",
    "economic_plan_hash",
    "prepared_message_base64",
    "prepared_message_hash",
    "simulation",
    "simulation_attestation_hash",
    "execution_commitment_hash",
    "signer",
    "constraints",
    "expires_at",
}
_SIMULATION_REQUIRED = {
    "rpc_provider_id",
    "genesis_hash",
    "slot",
    "commitment_level",
    "recent_blockhash",
    "last_valid_block_height",
    "simulated_at",
    "valid_until",
    "logs_hash",
    "pre_balances_hash",
    "post_balances_hash",
    "units_consumed",
    "fee_lamports",
    "success",
}
_SIMULATION_OPTIONAL = {"accounts_observed_hash", "programs_observed_hash"}
_CONSTRAINT_FIELDS = {"max_fee_lamports", "allowed_programs"}
_UNSIGNED_AUTHORIZATION_FIELDS = {
    "type",
    "protocol_version",
    "authorization_id",
    "execution_request_id",
    "execution_commitment_hash",
    "prepared_message_hash",
    "signer",
    "single_use",
    "issued_at",
    "expires_at",
}


class AuthorizationError(RuntimeError):
    """Base execution authorization failure."""


class AuthorizationInvalid(AuthorizationError):
    """Prepared execution or authoritative expectation failed validation."""


class AuthorizationConflict(AuthorizationError):
    """Another active or materially different authorization already exists."""


class AuthorizationExpired(AuthorizationError):
    """Authorization or one of its authority inputs has expired."""


class AuthorizationReplay(AuthorizationError):
    """A consumed authorization was presented again."""


class AuthorizationSignatureProvider(Protocol):
    """External boundary that signs canonical authorization bytes only."""

    def sign(self, payload: bytes) -> str: ...


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise AuthorizationInvalid(f"{path}: invalid UTC timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise AuthorizationInvalid(f"{path}: invalid UTC timestamp") from error
    return parsed.replace(tzinfo=UTC)


def _require_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AuthorizationInvalid(f"{path}: invalid identifier")
    return value


def _require_closed(
    value: Any,
    required: set[str],
    *,
    path: str,
    optional: set[str] | None = None,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AuthorizationInvalid(f"{path}: expected object")
    keys = set(value)
    missing = required - keys
    unknown = keys - required - (optional or set())
    if missing:
        raise AuthorizationInvalid(f"{path}: missing keys: {sorted(missing)}")
    if unknown:
        raise AuthorizationInvalid(f"{path}: unknown keys: {sorted(unknown)}")
    return value


def _require_safe_uint(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_SAFE_INTEGER:
        raise AuthorizationInvalid(f"{path}: expected safe unsigned integer")
    return value


def _decode_base58(value: str, path: str) -> bytes:
    number = 0
    try:
        for character in value:
            number = number * 58 + _BASE58_INDEX[character]
    except KeyError as error:
        raise AuthorizationInvalid(f"{path}: invalid base58") from error
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + payload


def _require_pubkey(value: Any, path: str) -> str:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        raise AuthorizationInvalid(f"{path}: invalid Solana public key")
    if len(_decode_base58(value, path)) != 32:
        raise AuthorizationInvalid(f"{path}: Solana public key must decode to 32 bytes")
    return value


def _validate_constraints(value: Any, path: str) -> dict[str, Any]:
    constraints = _require_closed(value, _CONSTRAINT_FIELDS, path=path)
    maximum_fee = _require_safe_uint(constraints["max_fee_lamports"], f"{path}.max_fee_lamports")
    programs = constraints["allowed_programs"]
    if not isinstance(programs, list) or not programs:
        raise AuthorizationInvalid(f"{path}.allowed_programs: expected non-empty array")
    normalized_programs = [
        _require_pubkey(program, f"{path}.allowed_programs[{index}]")
        for index, program in enumerate(programs)
    ]
    if len(set(normalized_programs)) != len(normalized_programs):
        raise AuthorizationInvalid(f"{path}.allowed_programs: duplicates are forbidden")
    return {
        "max_fee_lamports": maximum_fee,
        "allowed_programs": normalized_programs,
    }


def authorization_signing_payload(authorization: Mapping[str, Any]) -> bytes:
    """Return canonical bytes for an authorization without its signature."""

    unsigned = {
        key: value for key, value in authorization.items() if key != "authorization_signature"
    }
    _require_closed(unsigned, _UNSIGNED_AUTHORIZATION_FIELDS, path="$authorization")
    return canonicalize(unsigned)


class AuthorizationJournal:
    """SQLite journal for durable issuance, expiry, and consumption."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    execution_request_id TEXT NOT NULL,
                    obligation_id TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    authorization_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS execution_authorizations_request
                ON execution_authorizations (execution_request_id, state, expires_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS execution_authorizations_obligation
                ON execution_authorizations (obligation_id, state, expires_at)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def issue(
        self,
        authorization: Mapping[str, Any],
        *,
        obligation_id: str,
        input_fingerprint: str,
        now: datetime,
    ) -> dict[str, Any]:
        timestamp = _format_timestamp(now)
        authorization_id = authorization["authorization_id"]
        request_id = authorization["execution_request_id"]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE execution_authorizations
                SET state = 'expired'
                WHERE state = 'issued' AND expires_at <= ?
                """,
                (timestamp,),
            )
            existing = connection.execute(
                """
                SELECT * FROM execution_authorizations
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
            if existing is not None:
                if existing["input_fingerprint"] != input_fingerprint:
                    raise AuthorizationConflict(
                        "authorization_id was reused with different immutable inputs"
                    )
                if existing["state"] == "consumed":
                    raise AuthorizationReplay(authorization_id)
                if existing["state"] == "expired":
                    raise AuthorizationExpired(authorization_id)
                return json.loads(existing["authorization_json"])

            active = connection.execute(
                """
                SELECT authorization_id FROM execution_authorizations
                WHERE state = 'issued'
                  AND expires_at > ?
                  AND (execution_request_id = ? OR obligation_id = ?)
                LIMIT 1
                """,
                (timestamp, request_id, obligation_id),
            ).fetchone()
            if active is not None:
                raise AuthorizationConflict(
                    "request or obligation already has an active authorization"
                )
            connection.execute(
                """
                INSERT INTO execution_authorizations (
                    authorization_id,
                    execution_request_id,
                    obligation_id,
                    input_fingerprint,
                    authorization_json,
                    state,
                    issued_at,
                    expires_at
                ) VALUES (?, ?, ?, ?, ?, 'issued', ?, ?)
                """,
                (
                    authorization_id,
                    request_id,
                    obligation_id,
                    input_fingerprint,
                    _json(authorization),
                    authorization["issued_at"],
                    authorization["expires_at"],
                ),
            )
        return dict(authorization)

    def consume(self, authorization_id: str, *, now: datetime) -> dict[str, Any]:
        _require_identifier(authorization_id, "$authorization_id")
        timestamp = _format_timestamp(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM execution_authorizations
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise AuthorizationInvalid("authorization was not issued")
            if row["state"] == "consumed":
                raise AuthorizationReplay(authorization_id)
            if row["state"] == "expired" or row["expires_at"] <= timestamp:
                connection.execute(
                    """
                    UPDATE execution_authorizations SET state = 'expired'
                    WHERE authorization_id = ?
                    """,
                    (authorization_id,),
                )
                raise AuthorizationExpired(authorization_id)
            connection.execute(
                """
                UPDATE execution_authorizations
                SET state = 'consumed', consumed_at = ?
                WHERE authorization_id = ? AND state = 'issued'
                """,
                (timestamp, authorization_id),
            )
        return json.loads(row["authorization_json"])

    def state(self, authorization_id: str, *, now: datetime) -> str:
        _require_identifier(authorization_id, "$authorization_id")
        timestamp = _format_timestamp(now)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state, expires_at FROM execution_authorizations
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise AuthorizationInvalid("authorization was not issued")
            state = row["state"]
            if state == "issued" and row["expires_at"] <= timestamp:
                connection.execute(
                    """
                    UPDATE execution_authorizations SET state = 'expired'
                    WHERE authorization_id = ?
                    """,
                    (authorization_id,),
                )
                state = "expired"
        return str(state)


class ExecutionAuthorizationAuthority:
    """Verify prepared execution and issue exact, short-lived authorization."""

    def __init__(
        self,
        journal: AuthorizationJournal,
        *,
        signature_provider: AuthorizationSignatureProvider,
        max_ttl_seconds: int = MAX_AUTHORIZATION_TTL_SECONDS,
    ):
        if not 1 <= max_ttl_seconds <= MAX_AUTHORIZATION_TTL_SECONDS:
            raise ValueError("max_ttl_seconds must be between 1 and 60")
        self.journal = journal
        self.signature_provider = signature_provider
        self.max_ttl_seconds = max_ttl_seconds

    def issue(
        self,
        *,
        economic_plan: Mapping[str, Any],
        prepared_execution: Mapping[str, Any],
        authorization_id: str,
        expected_execution_request_id: str,
        expected_executor_id: str,
        expected_signer: str,
        expected_constraints: Mapping[str, Any],
        now: datetime,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        current = _utc(now).replace(microsecond=0)
        _require_identifier(authorization_id, "$authorization_id")
        _require_identifier(expected_execution_request_id, "$expected_execution_request_id")
        _require_identifier(expected_executor_id, "$expected_executor_id")
        _require_pubkey(expected_signer, "$expected_signer")
        if not 1 <= ttl_seconds <= self.max_ttl_seconds:
            raise AuthorizationInvalid("ttl_seconds exceeds the authority limit")

        plan = normalize_economic_plan(economic_plan)
        plan_expiry = _parse_timestamp(plan["expires_at"], "$economic_plan.expires_at")
        if plan_expiry <= current:
            raise AuthorizationExpired("economic plan has expired")

        prepared = _require_closed(
            prepared_execution,
            _PREPARED_FIELDS,
            path="$prepared_execution",
        )
        if prepared["type"] != "prepared_execution":
            raise AuthorizationInvalid("unsupported prepared execution type")
        if prepared["protocol_version"] != PROTOCOL_VERSION:
            raise AuthorizationInvalid("unsupported prepared execution version")
        if prepared["execution_request_id"] != expected_execution_request_id:
            raise AuthorizationInvalid("execution_request_id does not match Foundry authority")
        if prepared["executor_id"] != expected_executor_id:
            raise AuthorizationInvalid("executor_id does not match Foundry authority")
        if prepared["signer"] != expected_signer:
            raise AuthorizationInvalid("signer does not match Foundry authority")

        normalized_constraints = _validate_constraints(
            prepared["constraints"],
            "$prepared_execution.constraints",
        )
        authoritative_constraints = _validate_constraints(
            expected_constraints,
            "$expected_constraints",
        )
        if normalized_constraints != authoritative_constraints:
            raise AuthorizationInvalid("execution constraints do not match Foundry authority")

        expected_plan_hash = economic_plan_hash(plan)
        if prepared["economic_plan_hash"] != expected_plan_hash:
            raise AuthorizationInvalid("economic_plan_hash mismatch")

        try:
            message = base64.b64decode(
                prepared["prepared_message_base64"],
                validate=True,
            )
        except (TypeError, ValueError) as error:
            raise AuthorizationInvalid("prepared message is not canonical base64") from error
        if prepared_message_hash(message) != prepared["prepared_message_hash"]:
            raise AuthorizationInvalid("prepared_message_hash mismatch")

        simulation = _require_closed(
            prepared["simulation"],
            _SIMULATION_REQUIRED,
            optional=_SIMULATION_OPTIONAL,
            path="$prepared_execution.simulation",
        )
        if simulation["success"] is not True:
            raise AuthorizationInvalid("simulation did not succeed")
        for field in (
            "slot",
            "last_valid_block_height",
            "units_consumed",
            "fee_lamports",
        ):
            _require_safe_uint(simulation[field], f"$prepared_execution.simulation.{field}")
        if simulation["commitment_level"] not in {"confirmed", "finalized"}:
            raise AuthorizationInvalid("simulation commitment level is unsupported")
        simulation_time = _parse_timestamp(
            simulation["simulated_at"],
            "$prepared_execution.simulation.simulated_at",
        )
        simulation_expiry = _parse_timestamp(
            simulation["valid_until"],
            "$prepared_execution.simulation.valid_until",
        )
        if simulation_time > current:
            raise AuthorizationInvalid("simulation is from the future")
        if simulation_expiry <= current:
            raise AuthorizationExpired("simulation has expired")
        if simulation["fee_lamports"] > normalized_constraints["max_fee_lamports"]:
            raise AuthorizationInvalid("simulated fee exceeds the authorized maximum")
        if simulation_attestation_hash(simulation) != prepared["simulation_attestation_hash"]:
            raise AuthorizationInvalid("simulation_attestation_hash mismatch")

        prepared_expiry = _parse_timestamp(
            prepared["expires_at"],
            "$prepared_execution.expires_at",
        )
        if prepared_expiry <= current:
            raise AuthorizationExpired("prepared execution has expired")
        if prepared_expiry > plan_expiry or prepared_expiry > simulation_expiry:
            raise AuthorizationInvalid("prepared execution outlives its plan or simulation")

        commitment = {
            "protocol_version": prepared["protocol_version"],
            "normalization_profile": PROFILE,
            "execution_request_id": prepared["execution_request_id"],
            "obligation_id": plan["obligation_id"],
            "executor_id": prepared["executor_id"],
            "executor_version": prepared["executor_version"],
            "economic_plan_hash": prepared["economic_plan_hash"],
            "prepared_message_hash": prepared["prepared_message_hash"],
            "simulation_attestation_hash": prepared["simulation_attestation_hash"],
            "signer": prepared["signer"],
            "constraints": normalized_constraints,
            "expires_at": prepared["expires_at"],
        }
        if execution_commitment_hash(commitment) != prepared["execution_commitment_hash"]:
            raise AuthorizationInvalid("execution_commitment_hash mismatch")

        expires_at = min(
            current + timedelta(seconds=ttl_seconds),
            plan_expiry,
            simulation_expiry,
            prepared_expiry,
        )
        if expires_at <= current:
            raise AuthorizationExpired("no valid authorization window remains")
        unsigned_authorization: dict[str, Any] = {
            "type": "execution_authorization",
            "protocol_version": PROTOCOL_VERSION,
            "authorization_id": authorization_id,
            "execution_request_id": prepared["execution_request_id"],
            "execution_commitment_hash": prepared["execution_commitment_hash"],
            "prepared_message_hash": prepared["prepared_message_hash"],
            "signer": prepared["signer"],
            "single_use": True,
            "issued_at": _format_timestamp(current),
            "expires_at": _format_timestamp(expires_at),
        }
        signature = self.signature_provider.sign(
            authorization_signing_payload(unsigned_authorization)
        )
        if not isinstance(signature, str) or not 1 <= len(signature) <= 4096:
            raise AuthorizationInvalid("signature provider returned an invalid envelope")
        authorization = {
            **unsigned_authorization,
            "authorization_signature": signature,
        }
        fingerprint = sha256_digest(
            canonicalize(
                {
                    "economic_plan": plan,
                    "prepared_execution": dict(prepared),
                    "authorization": unsigned_authorization,
                }
            )
        )
        return self.journal.issue(
            authorization,
            obligation_id=plan["obligation_id"],
            input_fingerprint=fingerprint,
            now=current,
        )
