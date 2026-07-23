"""Persistent fake executor for protocol conformance and failure injection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .canonicalization import (
    PROFILE,
    PROTOCOL_VERSION,
    canonicalize,
    economic_plan_hash,
    execution_commitment_hash,
    normalize_economic_plan,
    prepared_message_hash,
    sha256_digest,
    simulation_attestation_hash,
)


class FakeExecutorError(RuntimeError):
    """Base error for fake executor protocol failures."""


class IdempotencyConflict(FakeExecutorError):
    """An identifier was reused with different immutable inputs."""


class AuthorizationInvalid(FakeExecutorError):
    """Authorization is malformed, unauthentic, expired, or not single-use."""


class AuthorizationMismatch(FakeExecutorError):
    """Authorization does not bind the stored prepared execution."""


class AuthorizationReplay(FakeExecutorError):
    """A consumed authorization was presented again."""


class ObligationAlreadyExecuted(FakeExecutorError):
    """The economic obligation already has a persisted effect."""


class ResponseLost(FakeExecutorError):
    """Execution committed durably but the response was intentionally lost."""


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str):
        raise AuthorizationInvalid(f"{path}: timestamp must be a string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise AuthorizationInvalid(f"{path}: invalid UTC timestamp") from error
    return parsed.replace(tzinfo=UTC)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _require_exact_keys(
    value: Mapping[str, Any],
    required: set[str],
    *,
    path: str,
) -> None:
    keys = set(value)
    missing = required - keys
    unknown = keys - required
    if missing:
        raise FakeExecutorError(f"{path}: missing keys: {sorted(missing)}")
    if unknown:
        raise FakeExecutorError(f"{path}: unknown keys: {sorted(unknown)}")


class FakeAuthorizationAuthority:
    """Issues deterministic HMAC attestations for local conformance only."""

    _FIELDS = {
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

    def __init__(self, key: bytes):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("fake authorization key must contain at least 32 bytes")
        self._key = key

    def issue(
        self,
        prepared: Mapping[str, Any],
        *,
        authorization_id: str,
        issued_at: str,
        expires_at: str,
        single_use: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "execution_authorization",
            "protocol_version": PROTOCOL_VERSION,
            "authorization_id": authorization_id,
            "execution_request_id": prepared["execution_request_id"],
            "execution_commitment_hash": prepared["execution_commitment_hash"],
            "prepared_message_hash": prepared["prepared_message_hash"],
            "signer": prepared["signer"],
            "single_use": single_use,
            "issued_at": issued_at,
            "expires_at": expires_at,
        }
        return {
            **payload,
            "authorization_signature": self._signature(payload),
        }

    def verify(self, authorization: Mapping[str, Any]) -> bool:
        if set(authorization) != self._FIELDS | {"authorization_signature"}:
            return False
        signature = authorization.get("authorization_signature")
        if not isinstance(signature, str):
            return False
        payload = {key: authorization[key] for key in self._FIELDS}
        return hmac.compare_digest(signature, self._signature(payload))

    def _signature(self, payload: Mapping[str, Any]) -> str:
        digest = hmac.new(self._key, canonicalize(payload), hashlib.sha256).hexdigest()
        return f"hmac-sha256:{digest}"


class FakeExternalExecutor:
    """SQLite-backed executor with deterministic effects and receipts."""

    _REQUEST_FIELDS = {
        "type",
        "protocol_version",
        "execution_request_id",
        "idempotency_key",
        "economic_plan",
        "economic_plan_hash",
        "economic_approval",
    }
    _AUTHORIZATION_FIELDS = FakeAuthorizationAuthority._FIELDS | {"authorization_signature"}

    def __init__(
        self,
        database: Path,
        *,
        authorization_authority: FakeAuthorizationAuthority,
        executor_id: str = "fake-solana-executor",
        executor_version: str = "0.1.0",
    ):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.authorization_authority = authorization_authority
        self.executor_id = executor_id
        self.executor_version = executor_version
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_request_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    obligation_id TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    prepared_json TEXT NOT NULL,
                    authorization_id TEXT,
                    transaction_signature TEXT,
                    receipt_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS authorization_consumptions (
                    authorization_id TEXT PRIMARY KEY,
                    execution_request_id TEXT NOT NULL,
                    consumed_at TEXT NOT NULL,
                    FOREIGN KEY (execution_request_id)
                        REFERENCES executions(execution_request_id)
                );

                CREATE TABLE IF NOT EXISTS effects (
                    obligation_id TEXT PRIMARY KEY,
                    execution_request_id TEXT NOT NULL UNIQUE,
                    applied_at TEXT NOT NULL,
                    FOREIGN KEY (execution_request_id)
                        REFERENCES executions(execution_request_id)
                );
                """
            )

    def prepare(
        self,
        request: Mapping[str, Any],
        *,
        simulation: Mapping[str, Any],
        signer: str,
        constraints: Mapping[str, Any],
        expires_at: str,
        now: datetime,
    ) -> dict[str, Any]:
        _require_exact_keys(request, self._REQUEST_FIELDS, path="$request")
        if request["type"] != "external_execution_request":
            raise FakeExecutorError("request type is not supported")
        if request["protocol_version"] != PROTOCOL_VERSION:
            raise FakeExecutorError("request protocol version is not supported")

        plan = normalize_economic_plan(request["economic_plan"])
        plan_hash = economic_plan_hash(plan)
        if request["economic_plan_hash"] != plan_hash:
            raise FakeExecutorError("economic plan hash mismatch")
        approval = request["economic_approval"]
        if not isinstance(approval, Mapping):
            raise FakeExecutorError("economic approval must be an object")
        if approval.get("economic_plan_hash") != plan_hash:
            raise FakeExecutorError("economic approval is bound to another plan")

        current = _utc(now)
        if _parse_timestamp(approval.get("expires_at"), "$approval.expires_at") <= current:
            raise FakeExecutorError("economic approval has expired")
        if _parse_timestamp(plan["expires_at"], "$plan.expires_at") <= current:
            raise FakeExecutorError("economic plan has expired")
        prepared_expiry = _parse_timestamp(expires_at, "$prepared.expires_at")
        if prepared_expiry <= current:
            raise FakeExecutorError("prepared execution has expired")

        if simulation.get("success") is not True:
            raise FakeExecutorError("simulation must succeed")
        simulation_valid_until = _parse_timestamp(
            simulation.get("valid_until"),
            "$simulation.valid_until",
        )
        if simulation_valid_until <= current:
            raise FakeExecutorError("simulation has expired")
        if prepared_expiry > simulation_valid_until:
            raise FakeExecutorError("prepared execution outlives its simulation")
        if prepared_expiry > _parse_timestamp(plan["expires_at"], "$plan.expires_at"):
            raise FakeExecutorError("prepared execution outlives its economic plan")

        message = b"foundry-fake-solana-message-v1\x00" + canonicalize(plan)
        message_hash = prepared_message_hash(message)
        simulation_hash = simulation_attestation_hash(simulation)
        commitment = {
            "protocol_version": PROTOCOL_VERSION,
            "normalization_profile": PROFILE,
            "execution_request_id": request["execution_request_id"],
            "obligation_id": plan["obligation_id"],
            "executor_id": self.executor_id,
            "executor_version": self.executor_version,
            "economic_plan_hash": plan_hash,
            "prepared_message_hash": message_hash,
            "simulation_attestation_hash": simulation_hash,
            "signer": signer,
            "constraints": dict(constraints),
            "expires_at": expires_at,
        }
        commitment_hash = execution_commitment_hash(commitment)
        prepared = {
            "type": "prepared_execution",
            "protocol_version": PROTOCOL_VERSION,
            "execution_request_id": request["execution_request_id"],
            "executor_id": self.executor_id,
            "executor_version": self.executor_version,
            "economic_plan_hash": plan_hash,
            "prepared_message_base64": base64.b64encode(message).decode("ascii"),
            "prepared_message_hash": message_hash,
            "simulation": dict(simulation),
            "simulation_attestation_hash": simulation_hash,
            "execution_commitment_hash": commitment_hash,
            "signer": signer,
            "constraints": dict(constraints),
            "expires_at": expires_at,
        }
        fingerprint = sha256_digest(
            canonicalize(
                {
                    "request": dict(request),
                    "simulation": dict(simulation),
                    "signer": signer,
                    "constraints": dict(constraints),
                    "expires_at": expires_at,
                }
            )
        )
        request_id = request["execution_request_id"]
        idempotency_key = request["idempotency_key"]
        obligation_id = plan["obligation_id"]
        timestamp = _format_timestamp(current)

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM executions
                WHERE execution_request_id = ? OR idempotency_key = ?
                """,
                (request_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["input_fingerprint"] != fingerprint:
                    raise IdempotencyConflict(
                        "request or idempotency key was reused with different inputs"
                    )
                return json.loads(existing["prepared_json"])
            effect = connection.execute(
                "SELECT 1 FROM effects WHERE obligation_id = ?",
                (obligation_id,),
            ).fetchone()
            if effect is not None:
                raise ObligationAlreadyExecuted(obligation_id)
            connection.execute(
                """
                INSERT INTO executions (
                    execution_request_id,
                    idempotency_key,
                    obligation_id,
                    input_fingerprint,
                    state,
                    prepared_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, 'prepared', ?, ?, ?)
                """,
                (
                    request_id,
                    idempotency_key,
                    obligation_id,
                    fingerprint,
                    _json(prepared),
                    timestamp,
                    timestamp,
                ),
            )
        return prepared

    def authorize_and_execute(
        self,
        authorization: Mapping[str, Any],
        *,
        now: datetime,
        fault: str | None = None,
    ) -> dict[str, Any]:
        if fault not in {None, "after_commit_before_response"}:
            raise ValueError(f"unsupported fault: {fault}")
        try:
            _require_exact_keys(
                authorization,
                self._AUTHORIZATION_FIELDS,
                path="$authorization",
            )
        except FakeExecutorError as error:
            raise AuthorizationInvalid(str(error)) from error
        if not self.authorization_authority.verify(authorization):
            raise AuthorizationInvalid("authorization signature is invalid")
        if authorization["type"] != "execution_authorization":
            raise AuthorizationInvalid("authorization type is not supported")
        if authorization["protocol_version"] != PROTOCOL_VERSION:
            raise AuthorizationInvalid("authorization version is not supported")
        if authorization["single_use"] is not True:
            raise AuthorizationInvalid("authorization must be single-use")

        current = _utc(now)
        issued_at = _parse_timestamp(authorization["issued_at"], "$authorization.issued_at")
        expires_at = _parse_timestamp(
            authorization["expires_at"],
            "$authorization.expires_at",
        )
        if issued_at > current:
            raise AuthorizationInvalid("authorization is not active yet")
        if expires_at <= current:
            raise AuthorizationInvalid("authorization has expired")

        request_id = authorization["execution_request_id"]
        authorization_id = authorization["authorization_id"]
        timestamp = _format_timestamp(current)

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            consumed = connection.execute(
                """
                SELECT 1 FROM authorization_consumptions
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
            if consumed is not None:
                raise AuthorizationReplay(authorization_id)

            execution = connection.execute(
                """
                SELECT * FROM executions
                WHERE execution_request_id = ?
                """,
                (request_id,),
            ).fetchone()
            if execution is None:
                raise AuthorizationMismatch("prepared execution does not exist")
            if execution["state"] == "confirmed":
                raise ObligationAlreadyExecuted(execution["obligation_id"])
            prepared = json.loads(execution["prepared_json"])
            self._verify_binding(
                authorization,
                prepared,
                current,
                obligation_id=execution["obligation_id"],
            )

            existing_effect = connection.execute(
                "SELECT 1 FROM effects WHERE obligation_id = ?",
                (execution["obligation_id"],),
            ).fetchone()
            if existing_effect is not None:
                raise ObligationAlreadyExecuted(execution["obligation_id"])

            connection.execute(
                """
                INSERT INTO authorization_consumptions (
                    authorization_id,
                    execution_request_id,
                    consumed_at
                ) VALUES (?, ?, ?)
                """,
                (authorization_id, request_id, timestamp),
            )
            connection.execute(
                """
                UPDATE executions
                SET state = 'authorized',
                    authorization_id = ?,
                    updated_at = ?
                WHERE execution_request_id = ?
                """,
                (authorization_id, timestamp, request_id),
            )

            transaction_signature = hashlib.sha256(
                (prepared["execution_commitment_hash"] + ":" + authorization_id).encode()
            ).hexdigest()
            receipt_without_hash = {
                "type": "external_execution_receipt",
                "protocol_version": PROTOCOL_VERSION,
                "execution_request_id": request_id,
                "execution_commitment_hash": prepared["execution_commitment_hash"],
                "prepared_message_hash": prepared["prepared_message_hash"],
                "transaction_signature": transaction_signature,
                "slot": 1,
                "confirmation_status": "confirmed",
                "observed_at": timestamp,
            }
            receipt = {
                **receipt_without_hash,
                "receipt_hash": sha256_digest(canonicalize(receipt_without_hash)),
            }
            connection.execute(
                """
                INSERT INTO effects (
                    obligation_id,
                    execution_request_id,
                    applied_at
                ) VALUES (?, ?, ?)
                """,
                (execution["obligation_id"], request_id, timestamp),
            )
            connection.execute(
                """
                UPDATE executions
                SET state = 'confirmed',
                    transaction_signature = ?,
                    receipt_json = ?,
                    updated_at = ?
                WHERE execution_request_id = ?
                """,
                (transaction_signature, _json(receipt), timestamp, request_id),
            )

        if fault == "after_commit_before_response":
            raise ResponseLost(request_id)
        return receipt

    def _verify_binding(
        self,
        authorization: Mapping[str, Any],
        prepared: Mapping[str, Any],
        current: datetime,
        *,
        obligation_id: str,
    ) -> None:
        exact_fields = (
            "execution_request_id",
            "execution_commitment_hash",
            "prepared_message_hash",
            "signer",
        )
        for field in exact_fields:
            if authorization[field] != prepared[field]:
                raise AuthorizationMismatch(f"authorization mismatch: {field}")
        try:
            message = base64.b64decode(
                prepared["prepared_message_base64"],
                validate=True,
            )
        except (KeyError, ValueError) as error:
            raise AuthorizationMismatch("stored prepared message is invalid") from error
        if prepared_message_hash(message) != prepared["prepared_message_hash"]:
            raise AuthorizationMismatch("stored prepared message hash mismatch")
        if (
            simulation_attestation_hash(prepared["simulation"])
            != prepared["simulation_attestation_hash"]
        ):
            raise AuthorizationMismatch("stored simulation attestation hash mismatch")
        reconstructed_commitment = {
            "protocol_version": prepared["protocol_version"],
            "normalization_profile": PROFILE,
            "execution_request_id": prepared["execution_request_id"],
            "obligation_id": obligation_id,
            "executor_id": prepared["executor_id"],
            "executor_version": prepared["executor_version"],
            "economic_plan_hash": prepared["economic_plan_hash"],
            "prepared_message_hash": prepared["prepared_message_hash"],
            "simulation_attestation_hash": prepared["simulation_attestation_hash"],
            "signer": prepared["signer"],
            "constraints": prepared["constraints"],
            "expires_at": prepared["expires_at"],
        }
        if (
            execution_commitment_hash(reconstructed_commitment)
            != prepared["execution_commitment_hash"]
        ):
            raise AuthorizationMismatch("stored execution commitment hash mismatch")
        if _parse_timestamp(prepared["expires_at"], "$prepared.expires_at") <= current:
            raise AuthorizationInvalid("prepared execution has expired")
        if _parse_timestamp(
            authorization["expires_at"],
            "$authorization.expires_at",
        ) > _parse_timestamp(prepared["expires_at"], "$prepared.expires_at"):
            raise AuthorizationInvalid("authorization outlives prepared execution")

    def status(self, execution_request_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            execution = connection.execute(
                """
                SELECT state, transaction_signature, updated_at
                FROM executions
                WHERE execution_request_id = ?
                """,
                (execution_request_id,),
            ).fetchone()
        if execution is None:
            raise FakeExecutorError("execution request does not exist")
        status: dict[str, Any] = {
            "type": "external_execution_status",
            "protocol_version": PROTOCOL_VERSION,
            "execution_request_id": execution_request_id,
            "state": execution["state"],
            "updated_at": execution["updated_at"],
        }
        if execution["transaction_signature"] is not None:
            status["transaction_signature"] = execution["transaction_signature"]
        return status

    def recover(
        self,
        execution_request_id: str,
        *,
        observed_at: datetime,
    ) -> dict[str, Any]:
        status = self.status(execution_request_id)
        if status["state"] == "confirmed":
            if self.receipt(execution_request_id) is None:
                raise FakeExecutorError("confirmed execution has no durable receipt")
            outcome = "confirmed"
            may_rematerialize = False
        elif status["state"] == "prepared":
            outcome = "failed_before_broadcast"
            may_rematerialize = True
        else:
            outcome = "unknown"
            may_rematerialize = False
        result: dict[str, Any] = {
            "type": "recovery_result",
            "protocol_version": PROTOCOL_VERSION,
            "execution_request_id": execution_request_id,
            "outcome": outcome,
            "may_rematerialize": may_rematerialize,
            "observed_at": _format_timestamp(_utc(observed_at)),
        }
        if "transaction_signature" in status:
            result["transaction_signature"] = status["transaction_signature"]
        return result

    def receipt(self, execution_request_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            execution = connection.execute(
                """
                SELECT receipt_json FROM executions
                WHERE execution_request_id = ?
                """,
                (execution_request_id,),
            ).fetchone()
        if execution is None:
            raise FakeExecutorError("execution request does not exist")
        if execution["receipt_json"] is None:
            return None
        receipt = json.loads(execution["receipt_json"])
        receipt_hash = receipt.pop("receipt_hash", None)
        expected_hash = sha256_digest(canonicalize(receipt))
        if receipt_hash != expected_hash:
            raise FakeExecutorError("persisted receipt integrity check failed")
        return {**receipt, "receipt_hash": receipt_hash}

    def effect_count(self, obligation_id: str) -> int:
        with self._connect() as connection:
            result = connection.execute(
                "SELECT COUNT(*) AS count FROM effects WHERE obligation_id = ?",
                (obligation_id,),
            ).fetchone()
        return int(result["count"])
