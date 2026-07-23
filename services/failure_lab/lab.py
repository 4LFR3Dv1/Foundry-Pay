"""SQLite-backed state machine for distributed execution failure injection."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from foundry_external_execution_protocol import canonicalize, sha256_digest


class FailureLabInvalid(RuntimeError):
    """A transition would violate the execution or recovery protocol."""


class BroadcastUnavailable(RuntimeError):
    """The transport proved that no broadcast was accepted."""


class BroadcastOutcomeUnknown(RuntimeError):
    """The transport cannot prove whether the broadcast was accepted."""


class InjectedCrash(RuntimeError):
    """The process stopped at a durable fault-injection boundary."""


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise FailureLabInvalid("invalid journal timestamp") from error
    return parsed.replace(tzinfo=UTC)


class SimulatedChain:
    """Durable-effect simulator with explicit transport failure modes."""

    def __init__(self) -> None:
        self.effects: dict[str, str] = {}
        self.calls = 0
        self.observation_mode: Literal["available", "unavailable", "unknown"] = "available"

    def broadcast(
        self,
        *,
        signature: str,
        obligation_id: str,
        mode: Literal[
            "success",
            "accepted_response_lost",
            "unavailable_before_acceptance",
            "unknown_without_effect",
        ] = "success",
    ) -> dict[str, Any]:
        self.calls += 1
        if mode == "unavailable_before_acceptance":
            raise BroadcastUnavailable("RPC unavailable before acceptance")
        if mode == "unknown_without_effect":
            raise BroadcastOutcomeUnknown("broadcast outcome is unknown")
        previous = self.effects.setdefault(obligation_id, signature)
        if previous != signature:
            raise FailureLabInvalid("duplicate economic effect attempted with another signature")
        if mode == "accepted_response_lost":
            raise BroadcastOutcomeUnknown("response lost after accepted broadcast")
        return {"signature": signature, "confirmation_status": "confirmed", "slot": 1}

    def observe(self, signature: str) -> Literal["confirmed", "not_found", "unknown"]:
        if self.observation_mode == "unavailable":
            raise BroadcastUnavailable("recovery RPC is unavailable")
        if self.observation_mode == "unknown":
            return "unknown"
        return "confirmed" if signature in self.effects.values() else "not_found"

    def effect_count(self, obligation_id: str) -> int:
        return int(obligation_id in self.effects)


class DurableExecutionLab:
    """Conservative execution journal: uncertainty is durable and non-retryable."""

    def __init__(self, database: Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_request_id TEXT PRIMARY KEY,
                    obligation_id TEXT NOT NULL UNIQUE,
                    message_hash TEXT NOT NULL,
                    blockhash_valid_until TEXT NOT NULL,
                    state TEXT NOT NULL,
                    signature TEXT,
                    signed_transaction_hash TEXT,
                    broadcast_count INTEGER NOT NULL DEFAULT 0,
                    recovery_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )

    def register(
        self,
        *,
        execution_request_id: str,
        obligation_id: str,
        message_hash: str,
        blockhash_valid_until: datetime,
        now: datetime,
    ) -> None:
        timestamp = _timestamp(now)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            unresolved = connection.execute(
                """
                SELECT state FROM executions
                WHERE obligation_id = ?
                """,
                (obligation_id,),
            ).fetchone()
            if unresolved is not None:
                raise FailureLabInvalid(
                    f"obligation already has execution state {unresolved['state']}"
                )
            connection.execute(
                """
                INSERT INTO executions (
                    execution_request_id, obligation_id, message_hash,
                    blockhash_valid_until, state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'authorized', ?, ?)
                """,
                (
                    execution_request_id,
                    obligation_id,
                    message_hash,
                    _timestamp(blockhash_valid_until),
                    timestamp,
                    timestamp,
                ),
            )
            self._append_event(
                connection,
                execution_request_id,
                "execution_registered",
                {"message_hash": message_hash, "obligation_id": obligation_id},
                timestamp,
            )

    def persist_signature(
        self,
        execution_request_id: str,
        *,
        signature: str,
        signed_transaction_hash: str,
        now: datetime,
        fault: str | None = None,
    ) -> None:
        if fault not in {None, "before_signature_persist"}:
            raise ValueError(f"unsupported fault: {fault}")
        if fault == "before_signature_persist":
            raise InjectedCrash("crash before signature persistence")
        timestamp = _timestamp(now)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_execution(connection, execution_request_id)
            if row["state"] == "signed":
                if (
                    row["signature"] == signature
                    and row["signed_transaction_hash"] == signed_transaction_hash
                ):
                    return
                raise FailureLabInvalid("signature persistence conflict")
            if row["state"] != "authorized":
                raise FailureLabInvalid(f"cannot persist signature from {row['state']}")
            connection.execute(
                """
                UPDATE executions
                SET state = 'signed', signature = ?, signed_transaction_hash = ?,
                    updated_at = ?
                WHERE execution_request_id = ?
                """,
                (signature, signed_transaction_hash, timestamp, execution_request_id),
            )
            self._append_event(
                connection,
                execution_request_id,
                "signature_persisted",
                {
                    "signature": signature,
                    "signed_transaction_hash": signed_transaction_hash,
                },
                timestamp,
            )

    def execute(
        self,
        execution_request_id: str,
        chain: SimulatedChain,
        *,
        now: datetime,
        mode: Literal[
            "success",
            "accepted_response_lost",
            "unavailable_before_acceptance",
            "unknown_without_effect",
        ] = "success",
        fault: str | None = None,
    ) -> dict[str, Any]:
        if fault not in {None, "after_broadcast_intent_before_call"}:
            raise ValueError(f"unsupported fault: {fault}")
        timestamp = _timestamp(now)
        expired = False
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_execution(connection, execution_request_id)
            if row["state"] == "needs_recovery":
                raise FailureLabInvalid("needs_recovery forbids automatic broadcast")
            if row["state"] != "signed":
                raise FailureLabInvalid(f"cannot broadcast from {row['state']}")
            if _parse_timestamp(row["blockhash_valid_until"]) <= now.astimezone(UTC):
                connection.execute(
                    """
                    UPDATE executions SET state = 'expired_requires_new_prepare',
                        updated_at = ? WHERE execution_request_id = ?
                    """,
                    (timestamp, execution_request_id),
                )
                self._append_event(
                    connection,
                    execution_request_id,
                    "blockhash_expired_before_broadcast",
                    {"broadcast_count": row["broadcast_count"]},
                    timestamp,
                )
                expired = True
            else:
                connection.execute(
                    """
                    UPDATE executions SET state = 'broadcast_in_flight',
                        broadcast_count = broadcast_count + 1, updated_at = ?
                    WHERE execution_request_id = ?
                    """,
                    (timestamp, execution_request_id),
                )
                self._append_event(
                    connection,
                    execution_request_id,
                    "broadcast_intent_persisted",
                    {"attempt": row["broadcast_count"] + 1, "signature": row["signature"]},
                    timestamp,
                )

        if expired:
            raise FailureLabInvalid("blockhash expired before broadcast")

        if fault == "after_broadcast_intent_before_call":
            self._mark_needs_recovery(
                execution_request_id,
                now=now,
                reason="process_crash_after_broadcast_intent",
            )
            raise InjectedCrash("crash after broadcast intent")

        try:
            receipt = chain.broadcast(
                signature=row["signature"],
                obligation_id=row["obligation_id"],
                mode=mode,
            )
        except BroadcastUnavailable:
            self._transition(
                execution_request_id,
                from_state="broadcast_in_flight",
                to_state="broadcast_failed_known",
                event_type="broadcast_rejected_before_acceptance",
                payload={"attempt": row["broadcast_count"] + 1},
                now=now,
            )
            raise
        except BroadcastOutcomeUnknown as error:
            self._mark_needs_recovery(
                execution_request_id,
                now=now,
                reason=str(error),
            )
            raise

        self._transition(
            execution_request_id,
            from_state="broadcast_in_flight",
            to_state="confirmed",
            event_type="broadcast_confirmed",
            payload={
                "attempt": row["broadcast_count"] + 1,
                "signature": receipt["signature"],
                "slot": receipt["slot"],
            },
            now=now,
        )
        return receipt

    def recover(
        self,
        execution_request_id: str,
        chain: SimulatedChain,
        *,
        now: datetime,
    ) -> dict[str, Any]:
        timestamp = _timestamp(now)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_execution(connection, execution_request_id)
            if row["state"] == "confirmed":
                return self._recovery_result(row, "confirmed", False, now)
            if row["state"] != "needs_recovery":
                raise FailureLabInvalid(f"cannot recover from {row['state']}")
            connection.execute(
                """
                UPDATE executions SET recovery_count = recovery_count + 1,
                    updated_at = ? WHERE execution_request_id = ?
                """,
                (timestamp, execution_request_id),
            )

        try:
            observation = chain.observe(row["signature"])
        except BroadcastUnavailable:
            observation = "unavailable"
        if observation == "confirmed":
            self._transition(
                execution_request_id,
                from_state="needs_recovery",
                to_state="confirmed",
                event_type="recovery_confirmed_signature",
                payload={"signature": row["signature"]},
                now=now,
            )
            refreshed = self.status(execution_request_id)
            return self._recovery_result(refreshed, "confirmed", False, now)

        event = (
            "recovery_source_unavailable"
            if observation == "unavailable"
            else "recovery_outcome_still_unknown"
        )
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._append_event(
                connection,
                execution_request_id,
                event,
                {"observation": observation},
                timestamp,
            )
        refreshed = self.status(execution_request_id)
        return self._recovery_result(refreshed, "needs_recovery", False, now)

    def status(self, execution_request_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection, connection:
            row = self._require_execution(connection, execution_request_id)
        return dict(row)

    def evidence(
        self,
        execution_request_id: str,
        *,
        scenario: str,
        economic_effect_count: int,
    ) -> dict[str, Any]:
        status = self.status(execution_request_id)
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT sequence, event_type, payload_json, previous_hash,
                       event_hash, recorded_at
                FROM events WHERE execution_request_id = ?
                ORDER BY sequence
                """,
                (execution_request_id,),
            ).fetchall()
        events = [
            {
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"],
                "recorded_at": row["recorded_at"],
            }
            for row in rows
        ]
        self._verify_event_chain(execution_request_id, events)
        may_rematerialize = status["state"] in {
            "authorized",
            "signed",
            "broadcast_failed_known",
            "expired_requires_new_prepare",
        }
        return {
            "type": "failure_scenario_evidence",
            "protocol_version": "1.0.0",
            "scenario": scenario,
            "execution_request_id": execution_request_id,
            "obligation_id": status["obligation_id"],
            "final_state": status["state"],
            "signature_persisted": status["signature"] is not None,
            "broadcast_count": status["broadcast_count"],
            "recovery_count": status["recovery_count"],
            "economic_effect_count": economic_effect_count,
            "may_rematerialize": may_rematerialize,
            "event_chain_head": events[-1]["event_hash"],
            "events": events,
        }

    def _mark_needs_recovery(
        self,
        execution_request_id: str,
        *,
        now: datetime,
        reason: str,
    ) -> None:
        self._transition(
            execution_request_id,
            from_state="broadcast_in_flight",
            to_state="needs_recovery",
            event_type="broadcast_outcome_unknown",
            payload={"reason": reason},
            now=now,
        )

    def _transition(
        self,
        execution_request_id: str,
        *,
        from_state: str,
        to_state: str,
        event_type: str,
        payload: Mapping[str, Any],
        now: datetime,
    ) -> None:
        timestamp = _timestamp(now)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_execution(connection, execution_request_id)
            if row["state"] != from_state:
                raise FailureLabInvalid(f"expected {from_state}, found {row['state']}")
            connection.execute(
                """
                UPDATE executions SET state = ?, updated_at = ?
                WHERE execution_request_id = ?
                """,
                (to_state, timestamp, execution_request_id),
            )
            self._append_event(
                connection,
                execution_request_id,
                event_type,
                payload,
                timestamp,
            )

    def _append_event(
        self,
        connection: sqlite3.Connection,
        execution_request_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        recorded_at: str,
    ) -> None:
        previous = connection.execute(
            """
            SELECT event_hash FROM events
            WHERE execution_request_id = ? ORDER BY sequence DESC LIMIT 1
            """,
            (execution_request_id,),
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else "genesis"
        event_body = {
            "execution_request_id": execution_request_id,
            "event_type": event_type,
            "payload": dict(payload),
            "previous_hash": previous_hash,
            "recorded_at": recorded_at,
        }
        event_hash = sha256_digest(canonicalize(event_body))
        connection.execute(
            """
            INSERT INTO events (
                execution_request_id, event_type, payload_json, previous_hash,
                event_hash, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                execution_request_id,
                event_type,
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
                previous_hash,
                event_hash,
                recorded_at,
            ),
        )

    def _verify_event_chain(
        self,
        execution_request_id: str,
        events: list[dict[str, Any]],
    ) -> None:
        previous_hash = "genesis"
        for event in events:
            if event["previous_hash"] != previous_hash:
                raise FailureLabInvalid("event chain previous hash mismatch")
            body = {
                "execution_request_id": execution_request_id,
                "event_type": event["event_type"],
                "payload": event["payload"],
                "previous_hash": event["previous_hash"],
                "recorded_at": event["recorded_at"],
            }
            if sha256_digest(canonicalize(body)) != event["event_hash"]:
                raise FailureLabInvalid("event chain hash mismatch")
            previous_hash = event["event_hash"]

    @staticmethod
    def _require_execution(
        connection: sqlite3.Connection,
        execution_request_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM executions WHERE execution_request_id = ?",
            (execution_request_id,),
        ).fetchone()
        if row is None:
            raise FailureLabInvalid("execution does not exist")
        return row

    @staticmethod
    def _recovery_result(
        row: Mapping[str, Any],
        outcome: str,
        may_rematerialize: bool,
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "type": "recovery_result",
            "protocol_version": "1.0.0",
            "execution_request_id": row["execution_request_id"],
            "outcome": outcome,
            "may_rematerialize": may_rematerialize,
            "broadcast_count": row["broadcast_count"],
            "observed_at": _timestamp(now),
        }
