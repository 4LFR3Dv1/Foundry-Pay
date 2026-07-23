"""SQLite counters and event log independent from the gateway journal."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundry_external_execution_protocol import canonicalize, sha256_digest

FAULT_MODES = {
    "pass",
    "reject_before_forward",
    "drop_before_forward",
    "drop_after_upstream",
    "delay_after_upstream",
    "return_null_status",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ChaosProxyStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS proxy_requests (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    upstream_response_hash TEXT,
                    received_at TEXT NOT NULL,
                    forwarded_at TEXT,
                    upstream_responded_at TEXT,
                    client_completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS fault_rules (
                    method TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    delay_ms INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proxy_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_sequence INTEGER,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def configure(self, method: str, mode: str, *, delay_ms: int = 0) -> None:
        if not method or not isinstance(method, str):
            raise ValueError("method is required")
        if mode not in FAULT_MODES:
            raise ValueError(f"unsupported fault mode: {mode}")
        if not isinstance(delay_ms, int) or isinstance(delay_ms, bool) or delay_ms < 0:
            raise ValueError("delay_ms must be an unsigned integer")
        timestamp = _now()
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO fault_rules (method, mode, delay_ms, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(method) DO UPDATE SET
                    mode = excluded.mode,
                    delay_ms = excluded.delay_ms,
                    updated_at = excluded.updated_at
                """,
                (method, mode, delay_ms, timestamp),
            )
            self._event(
                connection,
                None,
                "fault_rule_configured",
                {"method": method, "mode": mode, "delay_ms": delay_ms},
                timestamp,
            )

    def rule(self, method: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT mode, delay_ms FROM fault_rules WHERE method = ?",
                (method,),
            ).fetchone()
        if row is None:
            return {"mode": "pass", "delay_ms": 0}
        return dict(row)

    def receive(self, method: str, payload: bytes) -> int:
        timestamp = _now()
        request_hash = sha256_digest(payload)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO proxy_requests (
                    method, request_hash, state, received_at
                ) VALUES (?, ?, 'received', ?)
                """,
                (method, request_hash, timestamp),
            )
            assert cursor.lastrowid is not None
            sequence = int(cursor.lastrowid)
            self._event(
                connection,
                sequence,
                "request_received",
                {"method": method, "request_hash": request_hash},
                timestamp,
            )
            return sequence

    def transition(
        self,
        sequence: int,
        state: str,
        event_type: str,
        *,
        response: bytes | None = None,
    ) -> None:
        timestamp = _now()
        columns: dict[str, Any] = {"state": state}
        if state == "forwarded":
            columns["forwarded_at"] = timestamp
        elif state == "upstream_responded":
            columns["upstream_responded_at"] = timestamp
        elif state in {
            "client_response_delivered",
            "client_response_dropped",
            "rejected_before_forward",
            "client_response_dropped",
            "synthetic_response_delivered",
        }:
            columns["client_completed_at"] = timestamp
        if response is not None:
            columns["upstream_response_hash"] = sha256_digest(response)
        assignments = ", ".join(f"{name} = ?" for name in columns)
        values = [*columns.values(), sequence]
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            result = connection.execute(
                f"UPDATE proxy_requests SET {assignments} WHERE sequence = ?",  # noqa: S608
                values,
            )
            if result.rowcount != 1:
                raise RuntimeError("proxy request does not exist")
            payload: dict[str, Any] = {"state": state}
            if response is not None:
                payload["response_hash"] = sha256_digest(response)
            self._event(connection, sequence, event_type, payload, timestamp)

    def metrics(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT method, state, COUNT(*) AS count
                FROM proxy_requests GROUP BY method, state
                ORDER BY method, state
                """
            ).fetchall()
            totals = connection.execute(
                """
                SELECT method,
                    COUNT(*) AS requests_received,
                    SUM(CASE WHEN forwarded_at IS NOT NULL THEN 1 ELSE 0 END)
                        AS upstream_requests_forwarded,
                    SUM(CASE WHEN upstream_responded_at IS NOT NULL THEN 1 ELSE 0 END)
                        AS upstream_responses_received,
                    SUM(CASE WHEN state = 'client_response_delivered' THEN 1 ELSE 0 END)
                        AS client_responses_delivered,
                    SUM(CASE WHEN state = 'client_response_dropped' THEN 1 ELSE 0 END)
                        AS client_responses_dropped,
                    SUM(CASE WHEN state = 'rejected_before_forward' THEN 1 ELSE 0 END)
                        AS rejected_before_forward
                FROM proxy_requests GROUP BY method ORDER BY method
                """
            ).fetchall()
            head = connection.execute(
                "SELECT event_hash FROM proxy_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        return {
            "type": "chaos_proxy_metrics",
            "methods": [dict(row) for row in totals],
            "states": [dict(row) for row in rows],
            "event_chain_head": head["event_hash"] if head else "genesis",
        }

    def events(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT sequence, request_sequence, event_type, event_json,
                       previous_hash, event_hash, created_at
                FROM proxy_events ORDER BY sequence
                """
            ).fetchall()
        events = [
            {
                "sequence": row["sequence"],
                "request_sequence": (
                    row["request_sequence"] if row["request_sequence"] is not None else "control"
                ),
                "event_type": row["event_type"],
                "event": json.loads(row["event_json"]),
                "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        self.verify_events(events)
        return events

    @staticmethod
    def verify_events(events: list[dict[str, Any]]) -> None:
        previous = "genesis"
        for event in events:
            if event["previous_hash"] != previous:
                raise RuntimeError("proxy event chain previous hash mismatch")
            body = {
                "request_sequence": event["request_sequence"],
                "event_type": event["event_type"],
                "event": event["event"],
                "previous_hash": previous,
                "created_at": event["created_at"],
            }
            expected = sha256_digest(canonicalize(body))
            if event["event_hash"] != expected:
                raise RuntimeError("proxy event chain hash mismatch")
            previous = expected

    def _event(
        self,
        connection: sqlite3.Connection,
        request_sequence: int | None,
        event_type: str,
        event: dict[str, Any],
        created_at: str,
    ) -> None:
        previous_row = connection.execute(
            "SELECT event_hash FROM proxy_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous = previous_row["event_hash"] if previous_row else "genesis"
        normalized_request_sequence: int | str = (
            request_sequence if request_sequence is not None else "control"
        )
        body = {
            "request_sequence": normalized_request_sequence,
            "event_type": event_type,
            "event": event,
            "previous_hash": previous,
            "created_at": created_at,
        }
        event_hash = sha256_digest(canonicalize(body))
        connection.execute(
            """
            INSERT INTO proxy_events (
                request_sequence, event_type, event_json, previous_hash,
                event_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request_sequence,
                event_type,
                json.dumps(event, separators=(",", ":"), sort_keys=True),
                previous,
                event_hash,
                created_at,
            ),
        )
