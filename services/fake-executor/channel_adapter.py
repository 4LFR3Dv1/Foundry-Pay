"""Persistent adversarial fake adapter for SA-CHAN-000.

The adapter records caller-selected intent and technical outcomes. It has no
wallet, signer, Solana transport, or economic authority.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundry_channel_protocol.capabilities import (
    CAPABILITY_ID,
    EXECUTOR_ID,
    PROTOCOL_VERSION,
    CapabilityContractError,
    OperationStatus,
    capability_manifest,
    prepare_operation,
    validate_authorization,
    validate_observation,
    validate_recovery_request,
)
from foundry_channel_protocol.canonical import sha256_canonical_json


class FakeAdapterError(RuntimeError):
    """Stable fake-adapter state or persistence failure."""

    def __init__(self, code: str, stage: str, detail: str) -> None:
        self.code = code
        self.stage = stage
        self.detail = detail
        super().__init__(f"{stage}:{code}: {detail}")


def _timestamp(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"))


class FakeChannelAdapter:
    """SQLite-backed fixture runtime with explicit, non-default scenarios."""

    SCENARIOS = frozenset(
        {
            "preparation_only",
            "authorization_rejected",
            "definitive_pre_submission_failure",
            "submitted",
            "accepted",
            "lost_response",
            "recovery_confirmed",
            "recovery_inconclusive",
        }
    )

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    request_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL UNIQUE,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    prepared_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    authorization_json TEXT,
                    scenario TEXT,
                    submit_intent_count INTEGER NOT NULL DEFAULT 0,
                    automatic_resubmission_count INTEGER NOT NULL DEFAULT 0,
                    technical_receipt_json TEXT,
                    reconciled_result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS authorization_uses (
                    authorization_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL
                );
                """
            )

    def capabilities(self) -> dict[str, Any]:
        return capability_manifest()

    def prepare(self, request: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
        prepared = prepare_operation(request, now=now)
        request_hash = prepared["request_hash"]
        request_id = str(request["request_id"])
        operation_id = str(request["operation_id"])
        idempotency_key = str(request["idempotency_key"])
        timestamp = _timestamp(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM operations
                WHERE request_id = ? OR operation_id = ? OR idempotency_key = ?
                """,
                (request_id, operation_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise FakeAdapterError(
                        "idempotency_conflict",
                        "persistence",
                        "identifier was reused with different exact bytes",
                    )
                return json.loads(existing["prepared_json"])
            connection.execute(
                """
                INSERT INTO operations (
                    request_id, operation_id, idempotency_key, request_hash,
                    request_json, prepared_json, state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (
                    request_id,
                    operation_id,
                    idempotency_key,
                    request_hash,
                    _json(request),
                    _json(prepared),
                    timestamp,
                    timestamp,
                ),
            )
        return prepared

    def authorize(
        self,
        request_id: str,
        authorization: Mapping[str, Any],
        *,
        now: datetime,
        scenario: str,
    ) -> OperationStatus:
        if scenario not in self.SCENARIOS:
            raise FakeAdapterError("unsupported_scenario", "scenario", scenario)
        row = self._row(request_id)
        if scenario == "authorization_rejected":
            raise FakeAdapterError(
                "authorization_rejected",
                "authorization",
                "explicit adversarial scenario",
            )
        try:
            validated = validate_authorization(
                authorization,
                prepared=json.loads(row["prepared_json"]),
                now=now,
            )
        except CapabilityContractError as error:
            raise FakeAdapterError(error.code, error.stage, error.detail) from error
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            used = connection.execute(
                "SELECT request_id FROM authorization_uses WHERE authorization_id = ?",
                (validated["authorization_id"],),
            ).fetchone()
            if used is not None:
                raise FakeAdapterError(
                    "authorization_replay",
                    "authorization",
                    "authorization is single-use in the fixture",
                )
            current = connection.execute(
                "SELECT state FROM operations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if current["state"] != "prepared":
                raise FakeAdapterError(
                    "invalid_state",
                    "lifecycle",
                    f"cannot authorize from {current['state']}",
                )
            connection.execute(
                "INSERT INTO authorization_uses (authorization_id, request_id) VALUES (?, ?)",
                (validated["authorization_id"], request_id),
            )
            connection.execute(
                """
                UPDATE operations
                SET state = 'authorized', authorization_json = ?, scenario = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (_json(validated), scenario, _timestamp(now), request_id),
            )
        return self.status(request_id)

    def submit(self, request_id: str, *, now: datetime) -> OperationStatus:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM operations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise FakeAdapterError("unknown_request", "lifecycle", request_id)
            if row["state"] == "needs_recovery":
                raise FakeAdapterError(
                    "recovery_required",
                    "lifecycle",
                    "unknown outcome forbids another submission",
                )
            if row["state"] != "authorized":
                raise FakeAdapterError(
                    "invalid_state",
                    "lifecycle",
                    f"cannot submit from {row['state']}",
                )
            scenario = row["scenario"]
            if scenario == "definitive_pre_submission_failure":
                connection.execute(
                    """
                    UPDATE operations SET state = 'failed_definitive', updated_at = ?
                    WHERE request_id = ?
                    """,
                    (_timestamp(now), request_id),
                )
                return self._status_from_connection(connection, request_id)
            if scenario == "submitted":
                connection.execute(
                    """
                    UPDATE operations
                    SET state = 'submitted', submit_intent_count = submit_intent_count + 1,
                        updated_at = ?
                    WHERE request_id = ?
                    """,
                    (_timestamp(now), request_id),
                )
                return self._status_from_connection(connection, request_id)

            prepared = json.loads(row["prepared_json"])
            receipt_unsigned = {
                "type": "technical_channel_receipt",
                "protocol_version": PROTOCOL_VERSION,
                "capability_id": CAPABILITY_ID,
                "request_id": row["request_id"],
                "operation_id": row["operation_id"],
                "operation_commitment": prepared["operation_commitment"],
                "technical_identifier": f"fixture:{prepared['operation_commitment'][7:39]}",
                "technical_state": "confirmed",
                "executor_id": EXECUTOR_ID,
                "observed_at": _timestamp(now),
            }
            receipt = {
                **receipt_unsigned,
                "technical_receipt_hash": sha256_canonical_json(receipt_unsigned),
            }
            target = (
                "needs_recovery"
                if scenario in {"lost_response", "recovery_confirmed", "recovery_inconclusive"}
                else "confirmed"
            )
            stored_receipt = None if scenario == "recovery_inconclusive" else _json(receipt)
            connection.execute(
                """
                UPDATE operations
                SET state = ?, submit_intent_count = submit_intent_count + 1,
                    technical_receipt_json = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (target, stored_receipt, _timestamp(now), request_id),
            )
            return self._status_from_connection(connection, request_id)

    def recover(self, request_id: str, *, now: datetime) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM operations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise FakeAdapterError("unknown_request", "recovery", request_id)
            if row["state"] == "confirmed":
                outcome = "confirmed"
            elif row["state"] != "needs_recovery":
                raise FakeAdapterError(
                    "invalid_state",
                    "recovery",
                    f"cannot recover from {row['state']}",
                )
            elif row["scenario"] == "recovery_confirmed" or row["technical_receipt_json"]:
                outcome = "confirmed"
                connection.execute(
                    "UPDATE operations SET state = 'confirmed', updated_at = ? WHERE request_id = ?",
                    (_timestamp(now), request_id),
                )
            else:
                outcome = "unknown"
            refreshed = connection.execute(
                "SELECT * FROM operations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            result = {
                "type": "channel_recovery_result",
                "protocol_version": PROTOCOL_VERSION,
                "capability_id": CAPABILITY_ID,
                "request_id": request_id,
                "operation_id": refreshed["operation_id"],
                "outcome": outcome,
                "new_submission_attempted": False,
                "may_rematerialize": False,
                "observed_at": _timestamp(now),
            }
            if refreshed["technical_receipt_json"]:
                result["technical_receipt_hash"] = json.loads(refreshed["technical_receipt_json"])[
                    "technical_receipt_hash"
                ]
            return result

    def recover_from_contract(
        self,
        recovery_request: Mapping[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        validated = validate_recovery_request(recovery_request)
        row = self._row(validated["request_id"])
        if row["operation_id"] != validated["operation_id"]:
            raise FakeAdapterError(
                "recovery_mismatch",
                "recovery",
                "operation_id differs from the durable operation",
            )
        return self.recover(validated["request_id"], now=now)

    def reconcile(
        self,
        request_id: str,
        observation: Mapping[str, Any],
        *,
        now: datetime,
    ) -> OperationStatus:
        row = self._row(request_id)
        if row["state"] not in {"confirmed", "needs_review", "disputed"}:
            raise FakeAdapterError(
                "technical_confirmation_required",
                "reconciliation",
                "technical confirmation must precede reconciliation",
            )
        if row["technical_receipt_json"] is None:
            raise FakeAdapterError(
                "receipt_missing",
                "reconciliation",
                "no technical receipt is available",
            )
        receipt = json.loads(row["technical_receipt_json"])
        try:
            validated = validate_observation(observation, receipt=receipt)
        except CapabilityContractError as error:
            raise FakeAdapterError(error.code, error.stage, error.detail) from error
        outcome = validated["economic_outcome"]
        target = {"matched": "reconciled", "mismatch": "needs_review", "divergent": "disputed"}[
            outcome
        ]
        result = None
        if target == "reconciled":
            unsigned = {
                "type": "reconciled_channel_result",
                "protocol_version": PROTOCOL_VERSION,
                "capability_id": CAPABILITY_ID,
                "request_id": request_id,
                "operation_id": row["operation_id"],
                "technical_receipt_hash": receipt["technical_receipt_hash"],
                "observation_hash": sha256_canonical_json(validated),
                "economic_outcome": "matched",
                "reconciled_at": _timestamp(now),
            }
            result = {**unsigned, "result_hash": sha256_canonical_json(unsigned)}
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE operations SET state = ?, reconciled_result_json = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (target, None if result is None else _json(result), _timestamp(now), request_id),
            )
        return self.status(request_id)

    def status(self, request_id: str) -> OperationStatus:
        with self._connect() as connection:
            return self._status_from_connection(connection, request_id)

    def _status_from_connection(
        self,
        connection: sqlite3.Connection,
        request_id: str,
    ) -> OperationStatus:
        row = connection.execute(
            "SELECT * FROM operations WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise FakeAdapterError("unknown_request", "status", request_id)
        return OperationStatus(
            request_id=row["request_id"],
            operation_id=row["operation_id"],
            state=row["state"],
            submit_intent_count=int(row["submit_intent_count"]),
            automatic_resubmission_count=int(row["automatic_resubmission_count"]),
            updated_at=row["updated_at"],
            technical_receipt=(
                None
                if row["technical_receipt_json"] is None
                else json.loads(row["technical_receipt_json"])
            ),
            reconciled_result=(
                None
                if row["reconciled_result_json"] is None
                else json.loads(row["reconciled_result_json"])
            ),
        )

    def _row(self, request_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM operations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if row is None:
            raise FakeAdapterError("unknown_request", "status", request_id)
        return row
