"""Offline settlement, recovery, and reconciliation reference runtime.

This module validates caller-supplied channel snapshots and technical executor
artifacts. It does not assert that a snapshot or observation came from Solana.
Only an independently matching economic observation can produce a reconciled
receipt.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol

from foundry_external_execution_protocol import (
    economic_plan_hash,
    execution_commitment_hash,
    prepared_message_hash,
    simulation_attestation_hash,
)

from .canonical import sha256_canonical_json
from .channel import validate_channel


PROTOCOL_VERSION = "1.0.0"
_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PUBKEY = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_U64_MAX = 18_446_744_073_709_551_615
_JSON_SAFE_UNSIGNED_MAX = 9_007_199_254_740_991
_ZERO_HASH = "sha256:" + ("0" * 64)

_REQUEST_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "environment",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "channel_account",
        "epoch",
        "mint",
        "recipient_wallet",
        "settlement_id",
        "execution_request_id",
        "obligation_id",
        "idempotency_key",
        "requested_base_units",
        "activated_total_before",
        "settled_total_before",
        "vault_balance_before",
        "channel_snapshot_hash",
        "created_at",
        "expires_at",
    }
)
_COMMITMENT_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "settlement_request_hash",
        "execution_request_id",
        "execution_commitment_hash",
        "prepared_message_hash",
        "executor_id",
        "expected_signer",
        "expires_at",
    }
)
_AUTHORIZATION_FIELDS = frozenset(
    {
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
        "authorization_signature",
    }
)
_EXECUTOR_RECEIPT_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "execution_request_id",
        "execution_commitment_hash",
        "prepared_message_hash",
        "transaction_signature",
        "slot",
        "confirmation_status",
        "observed_at",
        "receipt_hash",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "source_id",
        "channel_id",
        "channel_account",
        "epoch",
        "mint",
        "destination",
        "transaction_signature",
        "settled_total_before",
        "settled_total_after",
        "vault_balance_before",
        "vault_balance_after",
        "recipient_balance_before",
        "recipient_balance_after",
        "observed_at",
        "observation_hash",
    }
)
_TERMINAL_RESERVATION_STATES = frozenset({"rejected", "failed_before_submission", "completed"})
_STATES = frozenset(
    {
        "requested",
        "validated",
        "execution_committed",
        "authorized",
        "submitted",
        "confirming",
        "reconciling",
        "completed",
        "rejected",
        "failed_before_submission",
        "needs_recovery",
        "needs_review",
        "disputed",
    }
)


class SettlementError(RuntimeError):
    """Stable, fail-closed settlement runtime error."""

    def __init__(self, code: str, field: str, detail: str) -> None:
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code} at {field}: {detail}")


class DefinitiveExecutorRejection(RuntimeError):
    """Injected executor proves rejection before accepting a submission."""

    def __init__(self, rejection_code: str) -> None:
        self.rejection_code = _identifier(rejection_code, "rejection_code")
        super().__init__(rejection_code)


class AuthorizationVerifier(Protocol):
    """Injected verification boundary for an execution authorization."""

    def verify(self, authorization: Mapping[str, Any]) -> bool: ...


class ObservationVerifier(Protocol):
    """Injected trust boundary for an independently sourced observation."""

    source_id: str

    def verify(self, observation: Mapping[str, Any]) -> bool: ...


class ExecutorPort(Protocol):
    """Technical executor boundary used by the offline reference runtime."""

    executor_id: str

    def authorize_and_execute(
        self,
        authorization: Mapping[str, Any],
        *,
        now: datetime,
        fault: str | None = None,
    ) -> Mapping[str, Any]: ...

    def recover(
        self,
        execution_request_id: str,
        *,
        observed_at: datetime,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class SettlementRequest:
    settlement_id: str
    request_hash: str
    channel_id: str
    epoch: int
    idempotency_key: str
    obligation_id: str
    execution_request_id: str
    requested_base_units: int
    activated_total_before: int
    settled_total_before: int
    vault_balance_before: int
    recipient_wallet: str
    expires_at: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SettlementExecutionCommitment:
    settlement_request_hash: str
    execution_request_id: str
    execution_commitment_hash: str
    prepared_message_hash: str
    executor_id: str
    expected_signer: str
    expires_at: str
    commitment_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": "settlement_execution_commitment",
            "protocol_version": PROTOCOL_VERSION,
            **asdict(self),
        }


@dataclass(frozen=True, slots=True)
class SettlementJournalEntry:
    settlement_id: str
    sequence: int
    state: str
    event_type: str
    event_hash: str
    previous_event_hash: str
    recorded_at: str
    payload: dict[str, Any]
    payload_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "settlement_journal_entry",
            "protocol_version": PROTOCOL_VERSION,
            **asdict(self),
        }


@dataclass(frozen=True, slots=True)
class TechnicalExecutionReceipt:
    settlement_id: str
    execution_request_id: str
    execution_commitment_hash: str
    prepared_message_hash: str
    outcome: str
    signature_status: str
    transaction_signature: str | None
    technical_status: str
    executor_receipt_hash: str | None
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "technical_execution_receipt",
            "protocol_version": PROTOCOL_VERSION,
            **{key: value for key, value in asdict(self).items() if value is not None},
        }


@dataclass(frozen=True, slots=True)
class SettlementObservation:
    source_id: str
    observation_hash: str
    channel_id: str
    epoch: int
    settled_total_after: int
    vault_balance_after: int
    recipient_balance_after: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReconciledSettlementReceipt:
    settlement_id: str
    settlement_request_hash: str
    execution_request_id: str
    obligation_id: str
    channel_id: str
    channel_account: str
    epoch: int
    mint: str
    destination: str
    requested_base_units: int
    settled_total_before: int
    settled_total_after: int
    vault_balance_before: int
    vault_balance_after: int
    transaction_signature: str
    observation_hashes: tuple[str, ...]
    reconciliation_status: str
    completed_at: str
    receipt_hash: str

    def to_dict(self) -> dict[str, Any]:
        value = {
            "type": "reconciled_settlement_receipt",
            "protocol_version": PROTOCOL_VERSION,
            **asdict(self),
        }
        value["observation_hashes"] = list(self.observation_hashes)
        for field in (
            "requested_base_units",
            "settled_total_before",
            "settled_total_after",
            "vault_balance_before",
            "vault_balance_after",
        ):
            value[field] = str(value[field])
        return value


@dataclass(frozen=True, slots=True)
class SettlementRecoveryRecord:
    settlement_id: str
    attempt: int
    outcome: str
    executor_id: str | None
    status_response_hash: str | None
    transaction_signature: str | None
    submit_intent_count: int
    automatic_second_submission_count: int
    observed_at: str
    detail: Mapping[str, Any] | None
    recovery_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "settlement_recovery_record",
            "protocol_version": PROTOCOL_VERSION,
            **{key: value for key, value in asdict(self).items() if value is not None},
        }


@dataclass(frozen=True, slots=True)
class SettlementRecord:
    settlement_id: str
    request_hash: str
    state: str
    submit_intent_count: int
    transaction_signature: str | None
    reconciled_receipt: ReconciledSettlementReceipt | None


def _reject(code: str, field: str, detail: str) -> NoReturn:
    raise SettlementError(code, field, detail)


def _closed(
    value: object,
    *,
    field: str,
    required: frozenset[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject("invalid_type", field, "expected an object")
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - required)
    if missing:
        _reject("missing_field", field, f"missing {', '.join(missing)}")
    if unknown:
        _reject("unknown_field", field, f"unknown {', '.join(unknown)}")
    if any(child is None for child in value.values()):
        _reject("null_forbidden", field, "null values are forbidden")
    return value


def _literal(value: object, expected: object, field: str) -> None:
    if value != expected or type(value) is not type(expected):
        _reject("invalid_literal", field, f"expected {expected!r}")


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _reject("invalid_identifier", field, "invalid closed identifier")
    return value


def _pubkey(value: object, field: str) -> str:
    if not isinstance(value, str) or _PUBKEY.fullmatch(value) is None:
        _reject("invalid_pubkey", field, "invalid public identifier")
    return value


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        _reject("invalid_hash", field, "expected sha256:<64 lowercase hex>")
    return value


def _amount(value: object, field: str, *, positive: bool = False) -> int:
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        _reject("invalid_amount", field, "expected canonical unsigned decimal string")
    parsed = int(value)
    if parsed > _U64_MAX:
        _reject("amount_out_of_range", field, "expected unsigned 64-bit amount")
    if positive and parsed == 0:
        _reject("zero_settlement", field, "settlement amount must be positive")
    return parsed


def _integer(value: object, field: str) -> int:
    if type(value) is not int or value < 0 or value > _JSON_SAFE_UNSIGNED_MAX:
        _reject("invalid_integer", field, "expected JSON-safe unsigned integer")
    return value


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        _reject("invalid_timestamp", field, "expected UTC seconds")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        _reject("invalid_timestamp", field, "invalid calendar timestamp")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        _reject("invalid_now", "now", "expected timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0)


def _format_time(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(value)


def channel_snapshot_hash(channel_snapshot: Mapping[str, Any]) -> str:
    """Hash a fully validated caller-supplied channel snapshot."""

    validate_channel(channel_snapshot)
    return _canonical_hash(channel_snapshot)


def validate_settlement_request(
    request_value: object,
    *,
    channel_snapshot: Mapping[str, Any],
    now: datetime,
) -> SettlementRequest:
    """Validate an economic request against an externally supplied snapshot."""

    projection = validate_channel(channel_snapshot)
    request = _closed(request_value, field="request", required=_REQUEST_FIELDS)
    _literal(request["type"], "settlement_request", "request.type")
    _literal(request["protocol_version"], PROTOCOL_VERSION, "request.protocol_version")
    _literal(request["environment"], "devnet", "request.environment")
    _literal(request["network"], "solana:devnet", "request.network")
    for field in (
        "genesis_hash",
        "program_id",
        "channel_account",
        "mint",
        "recipient_wallet",
    ):
        _pubkey(request[field], f"request.{field}")
    for field in (
        "channel_id",
        "settlement_id",
        "execution_request_id",
        "obligation_id",
        "idempotency_key",
    ):
        _identifier(request[field], f"request.{field}")
    _integer(request["epoch"], "request.epoch")
    _hash(request["channel_snapshot_hash"], "request.channel_snapshot_hash")
    requested = _amount(
        request["requested_base_units"], "request.requested_base_units", positive=True
    )
    activated = _amount(
        request["activated_total_before"],
        "request.activated_total_before",
    )
    settled = _amount(request["settled_total_before"], "request.settled_total_before")
    vault = _amount(request["vault_balance_before"], "request.vault_balance_before")
    created_at = _time(request["created_at"], "request.created_at")
    expires_at = _time(request["expires_at"], "request.expires_at")
    current = _utc(now)
    if expires_at <= created_at:
        _reject("invalid_request_window", "request.expires_at", "must follow created_at")
    if current < created_at:
        _reject("request_not_yet_valid", "request.created_at", "request is from the future")
    if current >= expires_at:
        _reject("request_expired", "request.expires_at", "request is expired")
    if expires_at > _time(channel_snapshot["expires_at"], "channel_snapshot.expires_at"):
        _reject(
            "request_outlives_channel",
            "request.expires_at",
            "must not outlive the supplied channel snapshot",
        )

    matched_fields = (
        "environment",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "channel_account",
        "epoch",
        "mint",
        "recipient_wallet",
    )
    for field in matched_fields:
        if request[field] != channel_snapshot.get(field):
            _reject("snapshot_context_mismatch", f"request.{field}", "does not match snapshot")
    expected_snapshot_hash = channel_snapshot_hash(channel_snapshot)
    if request["channel_snapshot_hash"] != expected_snapshot_hash:
        _reject(
            "snapshot_tampering",
            "request.channel_snapshot_hash",
            "does not hash the validated snapshot",
        )
    if activated != projection.activated_authorized_total_base_units:
        _reject(
            "snapshot_total_mismatch",
            "request.activated_total_before",
            "must come from the supplied channel snapshot",
        )
    if settled != projection.settled_total_base_units:
        _reject(
            "snapshot_total_mismatch",
            "request.settled_total_before",
            "must come from the supplied channel snapshot",
        )
    if vault != projection.vault_balance_base_units:
        _reject(
            "snapshot_total_mismatch",
            "request.vault_balance_before",
            "must come from the supplied channel snapshot",
        )
    liquidatable = activated - settled
    if requested > liquidatable:
        _reject("over_settlement", "request.requested_base_units", "exceeds activated right")
    if requested > vault:
        _reject("settlement_above_vault", "request.requested_base_units", "exceeds vault")
    if channel_snapshot["status"] not in {"active", "settling"}:
        _reject("settlement_lifecycle_forbidden", "channel_snapshot.status", "not settleable")
    request_hash = _canonical_hash(request)
    return SettlementRequest(
        settlement_id=request["settlement_id"],
        request_hash=request_hash,
        channel_id=request["channel_id"],
        epoch=request["epoch"],
        idempotency_key=request["idempotency_key"],
        obligation_id=request["obligation_id"],
        execution_request_id=request["execution_request_id"],
        requested_base_units=requested,
        activated_total_before=activated,
        settled_total_before=settled,
        vault_balance_before=vault,
        recipient_wallet=request["recipient_wallet"],
        expires_at=request["expires_at"],
    )


class SettlementRuntime:
    """SQLite reference runtime with durable intent, recovery, and reconciliation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA foreign_keys = ON")
        except Exception:
            connection.close()
            raise
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
                CREATE TABLE IF NOT EXISTS settlements (
                    settlement_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    obligation_id TEXT NOT NULL,
                    execution_request_id TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    snapshot_hash TEXT NOT NULL,
                    requested_amount INTEGER NOT NULL CHECK (requested_amount > 0),
                    activated_before INTEGER NOT NULL,
                    settled_before INTEGER NOT NULL,
                    vault_before INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    commitment_json TEXT,
                    commitment_hash TEXT,
                    authorization_json TEXT,
                    authorization_hash TEXT,
                    technical_receipt_json TEXT,
                    transaction_signature TEXT,
                    reconciled_receipt_json TEXT,
                    reconciled_receipt_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (channel_id, epoch, idempotency_key),
                    UNIQUE (channel_id, epoch, obligation_id)
                );

                CREATE TABLE IF NOT EXISTS submit_intents (
                    settlement_id TEXT PRIMARY KEY,
                    intent_count INTEGER NOT NULL CHECK (intent_count = 1),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (settlement_id) REFERENCES settlements(settlement_id)
                );

                CREATE TABLE IF NOT EXISTS settlement_events (
                    settlement_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    previous_event_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (settlement_id, sequence),
                    FOREIGN KEY (settlement_id) REFERENCES settlements(settlement_id)
                );

                CREATE TABLE IF NOT EXISTS settlement_recoveries (
                    settlement_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    recovery_json TEXT NOT NULL,
                    recovery_hash TEXT NOT NULL UNIQUE,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (settlement_id, attempt),
                    FOREIGN KEY (settlement_id) REFERENCES settlements(settlement_id)
                );
                """
            )

    def register_request(
        self,
        request_value: Mapping[str, Any],
        *,
        channel_snapshot: Mapping[str, Any],
        now: datetime,
    ) -> SettlementRecord:
        """Atomically validate, reserve, and journal an economic settlement."""

        supplied = _closed(request_value, field="request", required=_REQUEST_FIELDS)
        supplied_settlement_id = _identifier(
            supplied["settlement_id"],
            "request.settlement_id",
        )
        supplied_hash = _canonical_hash(supplied)
        with closing(self._connect()) as connection:
            existing_by_id = connection.execute(
                "SELECT * FROM settlements WHERE settlement_id = ?",
                (supplied_settlement_id,),
            ).fetchone()
        if existing_by_id is not None:
            if existing_by_id["request_hash"] != supplied_hash:
                _reject(
                    "idempotency_conflict",
                    "request.settlement_id",
                    "completed or existing settlement binds different canonical bytes",
                )
            return self._record_from_row(existing_by_id)

        result = validate_settlement_request(
            request_value,
            channel_snapshot=channel_snapshot,
            now=now,
        )
        timestamp = _format_time(now)
        request_json = _json(request_value)
        snapshot_json = _json(channel_snapshot)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT * FROM settlements
                    WHERE settlement_id = ?
                       OR (channel_id = ? AND epoch = ? AND idempotency_key = ?)
                    """,
                    (
                        result.settlement_id,
                        result.channel_id,
                        result.epoch,
                        result.idempotency_key,
                    ),
                ).fetchone()
                if existing is not None:
                    if existing["request_hash"] != result.request_hash:
                        _reject(
                            "idempotency_conflict",
                            "request.idempotency_key",
                            "same scope was reused with different canonical bytes",
                        )
                    connection.commit()
                    return self._record_from_row(existing)

                existing_obligation = connection.execute(
                    """
                    SELECT settlement_id, state FROM settlements
                    WHERE channel_id = ? AND epoch = ? AND obligation_id = ?
                    """,
                    (result.channel_id, result.epoch, result.obligation_id),
                ).fetchone()
                if existing_obligation is not None:
                    code = (
                        "obligation_needs_recovery"
                        if existing_obligation["state"] == "needs_recovery"
                        else "obligation_conflict"
                    )
                    _reject(
                        code,
                        "request.obligation_id",
                        "obligation already has a controlled settlement",
                    )

                latest_completed = connection.execute(
                    """
                    SELECT MAX(CAST(json_extract(reconciled_receipt_json,
                                                '$.settled_total_after') AS INTEGER))
                    AS settled_after
                    FROM settlements
                    WHERE channel_id = ? AND epoch = ? AND state = 'completed'
                    """,
                    (result.channel_id, result.epoch),
                ).fetchone()["settled_after"]
                if latest_completed is not None and result.settled_total_before < int(
                    latest_completed
                ):
                    _reject(
                        "stale_snapshot",
                        "request.settled_total_before",
                        "precedes a completed reconciled settlement",
                    )

                reserved = connection.execute(
                    f"""
                    SELECT COALESCE(SUM(requested_amount), 0) AS reserved
                    FROM settlements
                    WHERE channel_id = ? AND epoch = ?
                      AND state NOT IN ({",".join("?" for _ in _TERMINAL_RESERVATION_STATES)})
                    """,
                    (
                        result.channel_id,
                        result.epoch,
                        *_TERMINAL_RESERVATION_STATES,
                    ),
                ).fetchone()["reserved"]
                total_pending = int(reserved) + result.requested_base_units
                if result.settled_total_before + total_pending > result.activated_total_before:
                    _reject(
                        "concurrent_over_settlement",
                        "request.requested_base_units",
                        "aggregate reservation exceeds activated right",
                    )
                if total_pending > result.vault_balance_before:
                    _reject(
                        "concurrent_vault_exhaustion",
                        "request.requested_base_units",
                        "aggregate reservation exceeds observed vault",
                    )
                connection.execute(
                    """
                    INSERT INTO settlements (
                        settlement_id, channel_id, epoch, idempotency_key, obligation_id,
                        execution_request_id, request_hash, request_json, snapshot_json,
                        snapshot_hash, requested_amount, activated_before, settled_before,
                        vault_before, state, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'requested', ?, ?)
                    """,
                    (
                        result.settlement_id,
                        result.channel_id,
                        result.epoch,
                        result.idempotency_key,
                        result.obligation_id,
                        result.execution_request_id,
                        result.request_hash,
                        request_json,
                        snapshot_json,
                        request_value["channel_snapshot_hash"],
                        result.requested_base_units,
                        result.activated_total_before,
                        result.settled_total_before,
                        result.vault_balance_before,
                        timestamp,
                        timestamp,
                    ),
                )
                self._append_event(
                    connection,
                    result.settlement_id,
                    state="requested",
                    event_type="settlement_requested",
                    payload={"request_hash": result.request_hash},
                    recorded_at=timestamp,
                )
                connection.execute(
                    "UPDATE settlements SET state = 'validated' WHERE settlement_id = ?",
                    (result.settlement_id,),
                )
                self._append_event(
                    connection,
                    result.settlement_id,
                    state="validated",
                    event_type="request_validated",
                    payload={
                        "requested_base_units": str(result.requested_base_units),
                        "activated_total_before": str(result.activated_total_before),
                        "settled_total_before": str(result.settled_total_before),
                        "vault_balance_before": str(result.vault_balance_before),
                    },
                    recorded_at=timestamp,
                )
                connection.commit()
            except SettlementError:
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                _reject("idempotency_conflict", "request", type(error).__name__)
        return self.get(result.settlement_id)

    def external_execution_request(
        self,
        settlement_id: str,
        *,
        economic_approval: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Derive the existing External Execution Protocol request deterministically."""

        row = self._require_row(settlement_id)
        request = json.loads(row["request_json"])
        snapshot = json.loads(row["snapshot_json"])
        plan = {
            "protocol_version": PROTOCOL_VERSION,
            "normalization_profile": "foundry-pay-domain-v1",
            "obligation_id": request["obligation_id"],
            "network": request["network"],
            "capability": "solana.spl_transfer.v1",
            "asset": {
                "kind": "spl-token",
                "mint": request["mint"],
                "decimals": snapshot["decimals"],
            },
            "amount_base_units": request["requested_base_units"],
            "source": snapshot["vault_token_account"],
            "destination": request["recipient_wallet"],
            "expires_at": request["expires_at"],
        }
        plan_hash = economic_plan_hash(plan)
        if economic_approval.get("economic_plan_hash") != plan_hash:
            _reject(
                "economic_approval_mismatch",
                "economic_approval.economic_plan_hash",
                "does not bind the derived settlement plan",
            )
        return {
            "type": "external_execution_request",
            "protocol_version": PROTOCOL_VERSION,
            "execution_request_id": request["execution_request_id"],
            "idempotency_key": request["idempotency_key"],
            "economic_plan": plan,
            "economic_plan_hash": plan_hash,
            "economic_approval": dict(economic_approval),
        }

    def commit_execution(
        self,
        settlement_id: str,
        prepared_execution: Mapping[str, Any],
        *,
        expected_signer: str,
        now: datetime,
    ) -> SettlementExecutionCommitment:
        """Persist the exact prepared execution binding before authorization."""

        _pubkey(expected_signer, "expected_signer")
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._row_for_update(connection, settlement_id)
                self._ensure_time_not_regressed(row, timestamp)
                if row["state"] in {
                    "execution_committed",
                    "authorized",
                    "submitted",
                    "confirming",
                    "reconciling",
                    "completed",
                    "needs_recovery",
                    "needs_review",
                    "disputed",
                }:
                    existing = json.loads(row["commitment_json"])
                    candidate = self._execution_commitment(
                        row,
                        prepared_execution,
                        expected_signer=expected_signer,
                        now=now,
                    )
                    if existing != candidate:
                        _reject(
                            "commitment_conflict",
                            "prepared_execution",
                            "settlement already binds different exact bytes",
                        )
                    connection.commit()
                    return self._commitment_dataclass(existing)
                if row["state"] != "validated":
                    _reject("invalid_state", "settlement.state", "expected validated")
                commitment = self._execution_commitment(
                    row,
                    prepared_execution,
                    expected_signer=expected_signer,
                    now=now,
                )
                commitment_hash = _canonical_hash(commitment)
                connection.execute(
                    """
                    UPDATE settlements
                    SET state = 'execution_committed', commitment_json = ?,
                        commitment_hash = ?, updated_at = ?
                    WHERE settlement_id = ?
                    """,
                    (_json(commitment), commitment_hash, timestamp, settlement_id),
                )
                self._append_event(
                    connection,
                    settlement_id,
                    state="execution_committed",
                    event_type="execution_committed",
                    payload={
                        "commitment_hash": commitment_hash,
                        "prepared_message_hash": commitment["prepared_message_hash"],
                    },
                    recorded_at=timestamp,
                )
                connection.commit()
                return self._commitment_dataclass(commitment)
            except SettlementError:
                connection.rollback()
                raise

    def record_authorization(
        self,
        settlement_id: str,
        authorization: Mapping[str, Any],
        *,
        verifier: AuthorizationVerifier,
        now: datetime,
    ) -> SettlementRecord:
        """Verify and persist authorization before any submit intent."""

        value = _closed(
            authorization,
            field="authorization",
            required=_AUTHORIZATION_FIELDS,
        )
        _literal(value["type"], "execution_authorization", "authorization.type")
        _literal(value["protocol_version"], PROTOCOL_VERSION, "authorization.protocol_version")
        _literal(value["single_use"], True, "authorization.single_use")
        _identifier(value["authorization_id"], "authorization.authorization_id")
        _identifier(value["execution_request_id"], "authorization.execution_request_id")
        for field in ("execution_commitment_hash", "prepared_message_hash"):
            _hash(value[field], f"authorization.{field}")
        _pubkey(value["signer"], "authorization.signer")
        issued = _time(value["issued_at"], "authorization.issued_at")
        expires = _time(value["expires_at"], "authorization.expires_at")
        current = _utc(now)
        if issued > current or expires <= current or expires <= issued:
            _reject("authorization_expired", "authorization.expires_at", "invalid active window")
        try:
            verified = verifier.verify(value)
        except Exception as error:
            _reject("authorization_verifier_failed", "authorization", type(error).__name__)
        if verified is not True:
            _reject("authorization_invalid", "authorization", "signature verification failed")

        timestamp = _format_time(now)
        authorization_hash = _canonical_hash(value)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._row_for_update(connection, settlement_id)
                self._ensure_time_not_regressed(row, timestamp)
                if row["state"] == "authorized":
                    if row["authorization_hash"] != authorization_hash:
                        _reject(
                            "authorization_conflict",
                            "authorization",
                            "different authorization already persisted",
                        )
                    connection.commit()
                    return self._record_from_row(row)
                if row["state"] != "execution_committed":
                    _reject("invalid_state", "settlement.state", "expected execution_committed")
                commitment = json.loads(row["commitment_json"])
                for auth_field, commitment_field in (
                    ("execution_request_id", "execution_request_id"),
                    ("execution_commitment_hash", "execution_commitment_hash"),
                    ("prepared_message_hash", "prepared_message_hash"),
                    ("signer", "expected_signer"),
                ):
                    if value[auth_field] != commitment[commitment_field]:
                        _reject(
                            "authorization_binding_mismatch",
                            f"authorization.{auth_field}",
                            "does not bind the settlement commitment",
                        )
                if expires > _time(commitment["expires_at"], "commitment.expires_at"):
                    _reject(
                        "authorization_outlives_commitment",
                        "authorization.expires_at",
                        "must not outlive prepared execution",
                    )
                connection.execute(
                    """
                    UPDATE settlements
                    SET state = 'authorized', authorization_json = ?,
                        authorization_hash = ?, updated_at = ?
                    WHERE settlement_id = ?
                    """,
                    (_json(value), authorization_hash, timestamp, settlement_id),
                )
                self._append_event(
                    connection,
                    settlement_id,
                    state="authorized",
                    event_type="authorization_persisted",
                    payload={"authorization_hash": authorization_hash},
                    recorded_at=timestamp,
                )
                connection.commit()
            except SettlementError:
                connection.rollback()
                raise
        return self.get(settlement_id)

    def submit(
        self,
        settlement_id: str,
        *,
        executor: ExecutorPort,
        now: datetime,
        fault: str | None = None,
    ) -> TechnicalExecutionReceipt:
        """Persist one submit intent, then invoke the technical executor once."""

        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._row_for_update(connection, settlement_id)
                self._ensure_time_not_regressed(row, timestamp)
                if row["state"] in {
                    "submitted",
                    "confirming",
                    "reconciling",
                    "completed",
                    "needs_recovery",
                    "needs_review",
                    "disputed",
                }:
                    _reject(
                        "submission_already_attempted",
                        "settlement.state",
                        "automatic second submission is forbidden",
                    )
                if row["state"] != "authorized":
                    _reject("invalid_state", "settlement.state", "expected authorized")
                commitment = json.loads(row["commitment_json"])
                authorization = json.loads(row["authorization_json"])
                current = _utc(now)
                if current >= _time(
                    authorization["expires_at"],
                    "authorization.expires_at",
                ):
                    _reject(
                        "authorization_expired",
                        "authorization.expires_at",
                        "expired before submission",
                    )
                if current >= _time(commitment["expires_at"], "commitment.expires_at"):
                    _reject(
                        "prepared_execution_expired",
                        "commitment.expires_at",
                        "expired before submission",
                    )
                if executor.executor_id != commitment["executor_id"]:
                    _reject("executor_mismatch", "executor.executor_id", "not committed executor")
                connection.execute(
                    """
                    INSERT INTO submit_intents (settlement_id, intent_count, created_at)
                    VALUES (?, 1, ?)
                    """,
                    (settlement_id, timestamp),
                )
                connection.execute(
                    "UPDATE settlements SET state = 'submitted', updated_at = ? "
                    "WHERE settlement_id = ?",
                    (timestamp, settlement_id),
                )
                self._append_event(
                    connection,
                    settlement_id,
                    state="submitted",
                    event_type="submit_intent_persisted",
                    payload={"submit_intent_count": 1},
                    recorded_at=timestamp,
                )
                connection.commit()
            except SettlementError:
                connection.rollback()
                raise
            except sqlite3.IntegrityError:
                connection.rollback()
                _reject(
                    "submission_already_attempted",
                    "settlement_id",
                    "submit intent already exists",
                )

        try:
            raw_receipt = executor.authorize_and_execute(
                authorization,
                now=now,
                fault=fault,
            )
        except DefinitiveExecutorRejection as error:
            technical = TechnicalExecutionReceipt(
                settlement_id=settlement_id,
                execution_request_id=authorization["execution_request_id"],
                execution_commitment_hash=authorization["execution_commitment_hash"],
                prepared_message_hash=authorization["prepared_message_hash"],
                outcome="rejected",
                signature_status="unknown",
                transaction_signature=None,
                technical_status=error.rejection_code,
                executor_receipt_hash=None,
                observed_at=timestamp,
            )
            self._persist_technical(
                settlement_id,
                technical,
                state="rejected",
                event_type="executor_rejected_before_acceptance",
                now=now,
            )
            return technical
        except Exception:
            technical = TechnicalExecutionReceipt(
                settlement_id=settlement_id,
                execution_request_id=authorization["execution_request_id"],
                execution_commitment_hash=authorization["execution_commitment_hash"],
                prepared_message_hash=authorization["prepared_message_hash"],
                outcome="unknown",
                signature_status="unknown",
                transaction_signature=None,
                technical_status="unknown",
                executor_receipt_hash=None,
                observed_at=timestamp,
            )
            self._persist_technical(
                settlement_id,
                technical,
                state="needs_recovery",
                event_type="executor_response_unknown",
                now=now,
            )
            return technical

        try:
            technical = self._validate_executor_receipt(settlement_id, raw_receipt)
        except SettlementError:
            invalid = TechnicalExecutionReceipt(
                settlement_id=settlement_id,
                execution_request_id=authorization["execution_request_id"],
                execution_commitment_hash=authorization["execution_commitment_hash"],
                prepared_message_hash=authorization["prepared_message_hash"],
                outcome="unknown",
                signature_status="unknown",
                transaction_signature=None,
                technical_status="invalid_receipt",
                executor_receipt_hash=None,
                observed_at=timestamp,
            )
            self._persist_technical(
                settlement_id,
                invalid,
                state="needs_review",
                event_type="technical_receipt_rejected",
                now=now,
            )
            raise
        self._persist_technical(
            settlement_id,
            technical,
            state="reconciling",
            event_type="technical_receipt_persisted",
            now=now,
        )
        return technical

    def recover(
        self,
        settlement_id: str,
        *,
        executor: ExecutorPort,
        now: datetime,
    ) -> SettlementRecoveryRecord:
        """Query status without submitting or rematerializing another execution."""

        row = self._require_row(settlement_id)
        if row["state"] == "completed":
            records = self.recovery_records(settlement_id)
            if records:
                return records[-1]
            _reject("recovery_not_required", "settlement.state", "already completed")
        if row["state"] not in {"needs_recovery", "reconciling", "needs_review", "disputed"}:
            _reject("invalid_state", "settlement.state", "recovery is not allowed")
        commitment = json.loads(row["commitment_json"])
        if executor.executor_id != commitment["executor_id"]:
            _reject("executor_mismatch", "executor.executor_id", "not committed executor")
        try:
            raw_result = executor.recover(row["execution_request_id"], observed_at=now)
        except Exception:
            return self._record_recovery(
                settlement_id,
                outcome="unknown",
                executor_id=executor.executor_id,
                status_response_hash=None,
                transaction_signature=None,
                target_state="needs_recovery",
                now=now,
                extra={"reason": "executor_status_unavailable"},
            )
        try:
            result = self._normalize_recovery_result(row, raw_result)
        except SettlementError as error:
            self._record_recovery(
                settlement_id,
                outcome="invalid_status_response",
                executor_id=executor.executor_id,
                status_response_hash=None,
                transaction_signature=None,
                target_state="needs_review",
                now=now,
                extra={"validation_code": error.code, "validation_field": error.field},
            )
            raise
        status_response_hash = _canonical_hash(result)
        outcome = result.get("outcome")
        signature = result.get("transaction_signature")
        if outcome == "confirmed" and isinstance(signature, str) and signature:
            target_state = "reconciling"
        elif outcome == "failed_before_broadcast":
            target_state = "failed_before_submission"
            signature = None
        else:
            outcome = "unknown"
            target_state = "needs_recovery"
            signature = None
        return self._record_recovery(
            settlement_id,
            outcome=str(outcome),
            executor_id=executor.executor_id,
            status_response_hash=status_response_hash,
            transaction_signature=signature,
            target_state=target_state,
            now=now,
        )

    def record_provider_divergence(
        self,
        settlement_id: str,
        *,
        provider_ids: Sequence[str],
        now: datetime,
    ) -> SettlementRecoveryRecord:
        """Persist an explicit provider divergence without selecting a winner."""

        state = self.get(settlement_id).state
        if state not in {"needs_recovery", "reconciling", "needs_review", "disputed"}:
            _reject("invalid_state", "settlement.state", "provider review is not allowed")
        if len(set(provider_ids)) < 2:
            _reject("provider_divergence_unproven", "provider_ids", "requires two providers")
        for provider_id in provider_ids:
            _identifier(provider_id, "provider_ids")
        return self._record_recovery(
            settlement_id,
            outcome="provider_divergence",
            executor_id=None,
            status_response_hash=None,
            transaction_signature=None,
            target_state="disputed",
            now=now,
            extra={"provider_ids": sorted(set(provider_ids))},
        )

    def reconcile(
        self,
        settlement_id: str,
        observations: Sequence[Mapping[str, Any]],
        *,
        observation_verifiers: Mapping[str, ObservationVerifier],
        now: datetime,
    ) -> ReconciledSettlementReceipt | None:
        """Complete only when independent observations prove the exact effect."""

        if not observations:
            _reject("observation_required", "observations", "at least one observation required")
        timestamp = _format_time(now)
        normalized = [self._normalize_observation(value) for value in observations]
        sources = [value["source_id"] for value in normalized]
        if len(set(sources)) != len(sources):
            _reject("duplicate_observation_source", "observations", "source_id must be unique")
        for observation in normalized:
            source_id = observation["source_id"]
            verifier = observation_verifiers.get(source_id)
            if verifier is None:
                _reject(
                    "observation_verifier_missing",
                    "observation.source_id",
                    "no independent verifier configured for source",
                )
            if verifier.source_id != source_id:
                _reject(
                    "observation_verifier_mismatch",
                    "observation.source_id",
                    "verifier is bound to a different source",
                )
            try:
                verified = verifier.verify(observation)
            except Exception:
                verified = False
            if not verified:
                _reject(
                    "observation_unverified",
                    "observation.observation_hash",
                    "independent source verification failed",
                )
        fingerprints = {
            _canonical_hash(
                {
                    key: value
                    for key, value in observation.items()
                    if key not in {"source_id", "observation_hash", "observed_at"}
                }
            )
            for observation in normalized
        }
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._row_for_update(connection, settlement_id)
                self._ensure_time_not_regressed(row, timestamp)
                if row["state"] == "completed":
                    connection.commit()
                    return self._receipt_from_row(row)
                if row["state"] not in {"reconciling", "needs_review", "disputed"}:
                    _reject("invalid_state", "settlement.state", "expected reconciling")
                if len(fingerprints) > 1:
                    self._set_state(
                        connection,
                        settlement_id,
                        state="disputed",
                        event_type="provider_observations_diverged",
                        payload={"source_ids": sorted(sources)},
                        timestamp=timestamp,
                    )
                    connection.commit()
                    return None

                request = json.loads(row["request_json"])
                expected_after = row["settled_before"] + row["requested_amount"]
                expected_vault_after = row["vault_before"] - row["requested_amount"]
                mismatches: list[str] = []
                for observation in normalized:
                    if _time(
                        observation["observed_at"],
                        "observation.observed_at",
                    ) < _time(row["updated_at"], "settlement.updated_at"):
                        mismatches.append("observation_time")
                    expected = {
                        "channel_id": row["channel_id"],
                        "channel_account": request["channel_account"],
                        "epoch": row["epoch"],
                        "mint": request["mint"],
                        "destination": request["recipient_wallet"],
                        "transaction_signature": row["transaction_signature"],
                        "settled_total_before": str(row["settled_before"]),
                        "settled_total_after": str(expected_after),
                        "vault_balance_before": str(row["vault_before"]),
                        "vault_balance_after": str(expected_vault_after),
                    }
                    for field, expected_value in expected.items():
                        if observation[field] != expected_value:
                            mismatches.append(field)
                    recipient_before = int(observation["recipient_balance_before"])
                    recipient_after = int(observation["recipient_balance_after"])
                    if recipient_after - recipient_before != row["requested_amount"]:
                        mismatches.append("recipient_delta")
                if mismatches:
                    self._set_state(
                        connection,
                        settlement_id,
                        state="needs_review",
                        event_type="reconciliation_mismatch",
                        payload={"mismatches": sorted(set(mismatches))},
                        timestamp=timestamp,
                    )
                    connection.commit()
                    return None

                receipt_without_hash: dict[str, Any] = {
                    "type": "reconciled_settlement_receipt",
                    "protocol_version": PROTOCOL_VERSION,
                    "settlement_id": settlement_id,
                    "settlement_request_hash": row["request_hash"],
                    "execution_request_id": row["execution_request_id"],
                    "obligation_id": row["obligation_id"],
                    "channel_id": row["channel_id"],
                    "channel_account": request["channel_account"],
                    "epoch": row["epoch"],
                    "mint": request["mint"],
                    "destination": request["recipient_wallet"],
                    "requested_base_units": str(row["requested_amount"]),
                    "settled_total_before": str(row["settled_before"]),
                    "settled_total_after": str(expected_after),
                    "vault_balance_before": str(row["vault_before"]),
                    "vault_balance_after": str(expected_vault_after),
                    "transaction_signature": row["transaction_signature"],
                    "observation_hashes": sorted(
                        observation["observation_hash"] for observation in normalized
                    ),
                    "reconciliation_status": "reference_observation_matched",
                    "completed_at": timestamp,
                }
                receipt_hash = _canonical_hash(receipt_without_hash)
                receipt = {**receipt_without_hash, "receipt_hash": receipt_hash}
                connection.execute(
                    """
                    UPDATE settlements
                    SET state = 'completed', reconciled_receipt_json = ?,
                        reconciled_receipt_hash = ?, updated_at = ?
                    WHERE settlement_id = ?
                    """,
                    (_json(receipt), receipt_hash, timestamp, settlement_id),
                )
                self._append_event(
                    connection,
                    settlement_id,
                    state="completed",
                    event_type="economic_observation_reconciled",
                    payload={
                        "receipt_hash": receipt_hash,
                        "observation_hashes": receipt["observation_hashes"],
                    },
                    recorded_at=timestamp,
                )
                connection.commit()
                return self._receipt_dataclass(receipt)
            except SettlementError:
                connection.rollback()
                raise

    def get(self, settlement_id: str) -> SettlementRecord:
        return self._record_from_row(self._require_row(settlement_id))

    def journal(self, settlement_id: str) -> list[SettlementJournalEntry]:
        self._require_row(settlement_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT settlement_id, sequence, state, event_type, event_hash,
                       previous_event_hash, recorded_at, event_json
                FROM settlement_events
                WHERE settlement_id = ?
                ORDER BY sequence
                """,
                (settlement_id,),
            ).fetchall()
        entries: list[SettlementJournalEntry] = []
        for row in rows:
            value = dict(row)
            event = json.loads(value.pop("event_json"))
            entries.append(
                SettlementJournalEntry(
                    **value,
                    payload=event["payload"],
                    payload_hash=_canonical_hash(event["payload"]),
                )
            )
        return entries

    def recovery_records(self, settlement_id: str) -> list[SettlementRecoveryRecord]:
        self._require_row(settlement_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT recovery_json FROM settlement_recoveries
                WHERE settlement_id = ? ORDER BY attempt
                """,
                (settlement_id,),
            ).fetchall()
        return [self._recovery_dataclass(json.loads(row["recovery_json"])) for row in rows]

    def submit_intent_count(self, settlement_id: str) -> int:
        self._require_row(settlement_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT intent_count FROM submit_intents WHERE settlement_id = ?",
                (settlement_id,),
            ).fetchone()
        return 0 if row is None else int(row["intent_count"])

    def _execution_commitment(
        self,
        row: sqlite3.Row,
        prepared: Mapping[str, Any],
        *,
        expected_signer: str,
        now: datetime,
    ) -> dict[str, Any]:
        required = frozenset(
            {
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
        )
        value = _closed(prepared, field="prepared_execution", required=required)
        _literal(value["type"], "prepared_execution", "prepared_execution.type")
        _literal(value["protocol_version"], PROTOCOL_VERSION, "prepared_execution.protocol_version")
        if value["execution_request_id"] != row["execution_request_id"]:
            _reject(
                "execution_request_mismatch",
                "prepared_execution.execution_request_id",
                "does not match settlement",
            )
        for field in (
            "economic_plan_hash",
            "prepared_message_hash",
            "simulation_attestation_hash",
            "execution_commitment_hash",
        ):
            _hash(value[field], f"prepared_execution.{field}")
        _identifier(value["executor_id"], "prepared_execution.executor_id")
        if not isinstance(value["executor_version"], str) or not value["executor_version"]:
            _reject(
                "invalid_executor_version",
                "prepared_execution.executor_version",
                "required",
            )
        _pubkey(value["signer"], "prepared_execution.signer")
        if value["signer"] != expected_signer:
            _reject("signer_mismatch", "prepared_execution.signer", "not expected signer")
        expires = _time(value["expires_at"], "prepared_execution.expires_at")
        if expires <= _utc(now):
            _reject("prepared_execution_expired", "prepared_execution.expires_at", "expired")
        request = json.loads(row["request_json"])
        snapshot = json.loads(row["snapshot_json"])
        expected_plan = {
            "protocol_version": PROTOCOL_VERSION,
            "normalization_profile": "foundry-pay-domain-v1",
            "obligation_id": row["obligation_id"],
            "network": request["network"],
            "capability": "solana.spl_transfer.v1",
            "asset": {
                "kind": "spl-token",
                "mint": request["mint"],
                "decimals": snapshot["decimals"],
            },
            "amount_base_units": request["requested_base_units"],
            "source": snapshot["vault_token_account"],
            "destination": request["recipient_wallet"],
            "expires_at": request["expires_at"],
        }
        if value["economic_plan_hash"] != economic_plan_hash(expected_plan):
            _reject(
                "economic_plan_mismatch",
                "prepared_execution.economic_plan_hash",
                "does not bind the exact settlement economics",
            )
        encoded_message = value["prepared_message_base64"]
        if not isinstance(encoded_message, str) or not encoded_message:
            _reject(
                "invalid_prepared_message",
                "prepared_execution.prepared_message_base64",
                "expected canonical Base64",
            )
        try:
            message = base64.b64decode(encoded_message, validate=True)
        except (binascii.Error, ValueError):
            _reject(
                "invalid_prepared_message",
                "prepared_execution.prepared_message_base64",
                "invalid Base64",
            )
        if base64.b64encode(message).decode("ascii") != encoded_message:
            _reject(
                "invalid_prepared_message",
                "prepared_execution.prepared_message_base64",
                "non-canonical Base64",
            )
        if prepared_message_hash(message) != value["prepared_message_hash"]:
            _reject(
                "prepared_message_tampering",
                "prepared_execution.prepared_message_hash",
                "does not hash exact prepared bytes",
            )
        if not isinstance(value["simulation"], Mapping):
            _reject(
                "invalid_simulation",
                "prepared_execution.simulation",
                "expected object",
            )
        if simulation_attestation_hash(value["simulation"]) != value["simulation_attestation_hash"]:
            _reject(
                "simulation_tampering",
                "prepared_execution.simulation_attestation_hash",
                "does not hash exact simulation",
            )
        if not isinstance(value["constraints"], Mapping):
            _reject(
                "invalid_constraints",
                "prepared_execution.constraints",
                "expected object",
            )
        external_commitment = {
            "protocol_version": value["protocol_version"],
            "normalization_profile": "foundry-pay-domain-v1",
            "execution_request_id": value["execution_request_id"],
            "obligation_id": row["obligation_id"],
            "executor_id": value["executor_id"],
            "executor_version": value["executor_version"],
            "economic_plan_hash": value["economic_plan_hash"],
            "prepared_message_hash": value["prepared_message_hash"],
            "simulation_attestation_hash": value["simulation_attestation_hash"],
            "signer": value["signer"],
            "constraints": dict(value["constraints"]),
            "expires_at": value["expires_at"],
        }
        if execution_commitment_hash(external_commitment) != value["execution_commitment_hash"]:
            _reject(
                "execution_commitment_tampering",
                "prepared_execution.execution_commitment_hash",
                "does not hash exact executor commitment",
            )
        commitment = {
            "type": "settlement_execution_commitment",
            "protocol_version": PROTOCOL_VERSION,
            "settlement_request_hash": row["request_hash"],
            "execution_request_id": row["execution_request_id"],
            "execution_commitment_hash": value["execution_commitment_hash"],
            "prepared_message_hash": value["prepared_message_hash"],
            "executor_id": value["executor_id"],
            "expected_signer": expected_signer,
            "expires_at": value["expires_at"],
        }
        _closed(commitment, field="commitment", required=_COMMITMENT_FIELDS)
        return commitment

    def _validate_executor_receipt(
        self,
        settlement_id: str,
        raw_receipt: Mapping[str, Any],
    ) -> TechnicalExecutionReceipt:
        value = _closed(
            raw_receipt,
            field="executor_receipt",
            required=_EXECUTOR_RECEIPT_FIELDS,
        )
        _literal(value["type"], "external_execution_receipt", "executor_receipt.type")
        _literal(
            value["protocol_version"],
            PROTOCOL_VERSION,
            "executor_receipt.protocol_version",
        )
        receipt_hash = _hash(value["receipt_hash"], "executor_receipt.receipt_hash")
        unsigned = {key: child for key, child in value.items() if key != "receipt_hash"}
        if _canonical_hash(unsigned) != receipt_hash:
            _reject("technical_receipt_tampering", "executor_receipt.receipt_hash", "mismatch")
        row = self._require_row(settlement_id)
        commitment = json.loads(row["commitment_json"])
        for receipt_field, expected in (
            ("execution_request_id", row["execution_request_id"]),
            ("execution_commitment_hash", commitment["execution_commitment_hash"]),
            ("prepared_message_hash", commitment["prepared_message_hash"]),
        ):
            if value[receipt_field] != expected:
                _reject(
                    "technical_receipt_mismatch",
                    f"executor_receipt.{receipt_field}",
                    "does not match committed execution",
                )
        if value["confirmation_status"] not in {"confirmed", "finalized"}:
            _reject(
                "technical_receipt_unconfirmed",
                "executor_receipt.confirmation_status",
                "unsupported technical status",
            )
        _integer(value["slot"], "executor_receipt.slot")
        _time(value["observed_at"], "executor_receipt.observed_at")
        signature = value["transaction_signature"]
        if not isinstance(signature, str) or not signature:
            _reject("invalid_signature", "executor_receipt.transaction_signature", "required")
        return TechnicalExecutionReceipt(
            settlement_id=settlement_id,
            execution_request_id=value["execution_request_id"],
            execution_commitment_hash=value["execution_commitment_hash"],
            prepared_message_hash=value["prepared_message_hash"],
            outcome="accepted",
            signature_status="known",
            transaction_signature=signature,
            technical_status=value["confirmation_status"],
            executor_receipt_hash=receipt_hash,
            observed_at=value["observed_at"],
        )

    def _persist_technical(
        self,
        settlement_id: str,
        technical: TechnicalExecutionReceipt,
        *,
        state: str,
        event_type: str,
        now: datetime,
    ) -> None:
        timestamp = _format_time(now)
        persisted_state = "confirming" if state == "reconciling" else state
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._row_for_update(connection, settlement_id)
                if row["state"] != "submitted":
                    _reject("invalid_state", "settlement.state", "expected submitted")
                connection.execute(
                    """
                    UPDATE settlements
                    SET state = ?, technical_receipt_json = ?,
                        transaction_signature = ?, updated_at = ?
                    WHERE settlement_id = ?
                    """,
                    (
                        persisted_state,
                        _json(technical.to_dict()),
                        technical.transaction_signature,
                        timestamp,
                        settlement_id,
                    ),
                )
                self._append_event(
                    connection,
                    settlement_id,
                    state=persisted_state,
                    event_type=event_type,
                    payload={
                        "outcome": technical.outcome,
                        "signature_status": technical.signature_status,
                        **(
                            {"executor_receipt_hash": technical.executor_receipt_hash}
                            if technical.executor_receipt_hash is not None
                            else {}
                        ),
                    },
                    recorded_at=timestamp,
                )
                if state == "reconciling":
                    connection.execute(
                        """
                        UPDATE settlements SET state = 'reconciling', updated_at = ?
                        WHERE settlement_id = ?
                        """,
                        (timestamp, settlement_id),
                    )
                    self._append_event(
                        connection,
                        settlement_id,
                        state="reconciling",
                        event_type="independent_reconciliation_required",
                        payload={
                            "technical_status": technical.technical_status,
                            "economic_completion": False,
                        },
                        recorded_at=timestamp,
                    )
                connection.commit()
            except SettlementError:
                connection.rollback()
                raise

    def _record_recovery(
        self,
        settlement_id: str,
        *,
        outcome: str,
        executor_id: str | None,
        status_response_hash: str | None,
        transaction_signature: str | None,
        target_state: str,
        now: datetime,
        extra: Mapping[str, Any] | None = None,
    ) -> SettlementRecoveryRecord:
        timestamp = _format_time(now)
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._row_for_update(connection, settlement_id)
                intent = connection.execute(
                    "SELECT intent_count FROM submit_intents WHERE settlement_id = ?",
                    (settlement_id,),
                ).fetchone()
                submit_count = 0 if intent is None else int(intent["intent_count"])
                attempt = (
                    int(
                        connection.execute(
                            """
                        SELECT COALESCE(MAX(attempt), 0) AS attempt
                        FROM settlement_recoveries WHERE settlement_id = ?
                        """,
                            (settlement_id,),
                        ).fetchone()["attempt"]
                    )
                    + 1
                )
                unsigned: dict[str, Any] = {
                    "type": "settlement_recovery_record",
                    "protocol_version": PROTOCOL_VERSION,
                    "settlement_id": settlement_id,
                    "attempt": attempt,
                    "outcome": outcome,
                    "submit_intent_count": submit_count,
                    "automatic_second_submission_count": 0,
                    "observed_at": timestamp,
                }
                if executor_id is not None:
                    unsigned["executor_id"] = executor_id
                if status_response_hash is not None:
                    unsigned["status_response_hash"] = status_response_hash
                if transaction_signature is not None:
                    unsigned["transaction_signature"] = transaction_signature
                if extra:
                    unsigned["detail"] = dict(extra)
                recovery_hash = _canonical_hash(unsigned)
                record = SettlementRecoveryRecord(
                    settlement_id=settlement_id,
                    attempt=attempt,
                    outcome=outcome,
                    executor_id=executor_id,
                    status_response_hash=status_response_hash,
                    transaction_signature=transaction_signature,
                    submit_intent_count=submit_count,
                    automatic_second_submission_count=0,
                    observed_at=timestamp,
                    detail=dict(extra) if extra else None,
                    recovery_hash=recovery_hash,
                )
                connection.execute(
                    """
                    INSERT INTO settlement_recoveries (
                        settlement_id, attempt, recovery_json, recovery_hash, observed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        settlement_id,
                        attempt,
                        _json(record.to_dict()),
                        recovery_hash,
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    UPDATE settlements SET state = ?, transaction_signature = COALESCE(?, transaction_signature),
                        updated_at = ? WHERE settlement_id = ?
                    """,
                    (target_state, transaction_signature, timestamp, settlement_id),
                )
                self._append_event(
                    connection,
                    settlement_id,
                    state=target_state,
                    event_type="recovery_observed",
                    payload={
                        "outcome": outcome,
                        "recovery_hash": recovery_hash,
                        "submit_intent_count": submit_count,
                        **(
                            {"status_response_hash": status_response_hash}
                            if status_response_hash is not None
                            else {}
                        ),
                        **(dict(extra) if extra else {}),
                    },
                    recorded_at=timestamp,
                )
                connection.commit()
                return record
            except SettlementError:
                connection.rollback()
                raise

    def _normalize_recovery_result(
        self,
        row: sqlite3.Row,
        value: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            _reject("invalid_recovery_result", "recovery_result", "expected object")
        required = {
            "type",
            "protocol_version",
            "execution_request_id",
            "outcome",
            "may_rematerialize",
            "observed_at",
        }
        if value.get("outcome") == "confirmed":
            required.add("transaction_signature")
        result = _closed(value, field="recovery_result", required=frozenset(required))
        _literal(result["type"], "recovery_result", "recovery_result.type")
        _literal(
            result["protocol_version"],
            PROTOCOL_VERSION,
            "recovery_result.protocol_version",
        )
        if result["execution_request_id"] != row["execution_request_id"]:
            _reject(
                "recovery_request_mismatch",
                "recovery_result.execution_request_id",
                "does not match committed execution",
            )
        outcome = result["outcome"]
        if outcome not in {"confirmed", "failed_before_broadcast", "unknown"}:
            _reject(
                "invalid_recovery_outcome",
                "recovery_result.outcome",
                "unsupported outcome",
            )
        may_rematerialize = result["may_rematerialize"]
        if not isinstance(may_rematerialize, bool):
            _reject(
                "invalid_recovery_result",
                "recovery_result.may_rematerialize",
                "expected boolean",
            )
        if outcome == "failed_before_broadcast" and not may_rematerialize:
            _reject(
                "invalid_recovery_result",
                "recovery_result.may_rematerialize",
                "failed-before-broadcast must be explicit",
            )
        if outcome != "failed_before_broadcast" and may_rematerialize:
            _reject(
                "unsafe_recovery_result",
                "recovery_result.may_rematerialize",
                "ambiguous or confirmed result cannot permit rematerialization",
            )
        if outcome == "confirmed":
            signature = result["transaction_signature"]
            if not isinstance(signature, str) or not signature:
                _reject(
                    "invalid_signature",
                    "recovery_result.transaction_signature",
                    "required for confirmed result",
                )
        _time(result["observed_at"], "recovery_result.observed_at")
        return dict(result)

    def _normalize_observation(self, value: Mapping[str, Any]) -> dict[str, Any]:
        observation = _closed(
            value,
            field="observation",
            required=_OBSERVATION_FIELDS,
        )
        _literal(observation["type"], "settlement_observation", "observation.type")
        _literal(
            observation["protocol_version"],
            PROTOCOL_VERSION,
            "observation.protocol_version",
        )
        _identifier(observation["source_id"], "observation.source_id")
        _identifier(observation["channel_id"], "observation.channel_id")
        _pubkey(observation["channel_account"], "observation.channel_account")
        _integer(observation["epoch"], "observation.epoch")
        _pubkey(observation["mint"], "observation.mint")
        _pubkey(observation["destination"], "observation.destination")
        if (
            not isinstance(observation["transaction_signature"], str)
            or not observation["transaction_signature"]
        ):
            _reject(
                "invalid_signature",
                "observation.transaction_signature",
                "required",
            )
        for field in (
            "settled_total_before",
            "settled_total_after",
            "vault_balance_before",
            "vault_balance_after",
            "recipient_balance_before",
            "recipient_balance_after",
        ):
            _amount(observation[field], f"observation.{field}")
        _time(observation["observed_at"], "observation.observed_at")
        supplied_hash = _hash(observation["observation_hash"], "observation.observation_hash")
        unsigned = {key: child for key, child in observation.items() if key != "observation_hash"}
        if _canonical_hash(unsigned) != supplied_hash:
            _reject("observation_tampering", "observation.observation_hash", "mismatch")
        return dict(observation)

    def _set_state(
        self,
        connection: sqlite3.Connection,
        settlement_id: str,
        *,
        state: str,
        event_type: str,
        payload: Mapping[str, Any],
        timestamp: str,
    ) -> None:
        connection.execute(
            "UPDATE settlements SET state = ?, updated_at = ? WHERE settlement_id = ?",
            (state, timestamp, settlement_id),
        )
        self._append_event(
            connection,
            settlement_id,
            state=state,
            event_type=event_type,
            payload=payload,
            recorded_at=timestamp,
        )

    @staticmethod
    def _ensure_time_not_regressed(row: sqlite3.Row, timestamp: str) -> None:
        if _time(timestamp, "timestamp") < _time(row["updated_at"], "settlement.updated_at"):
            _reject(
                "journal_time_regressed",
                "now",
                "must not precede the persisted settlement timestamp",
            )

    def _append_event(
        self,
        connection: sqlite3.Connection,
        settlement_id: str,
        *,
        state: str,
        event_type: str,
        payload: Mapping[str, Any],
        recorded_at: str,
    ) -> None:
        if state not in _STATES:
            raise AssertionError(f"unsupported state: {state}")
        previous = connection.execute(
            """
            SELECT sequence, event_hash FROM settlement_events
            WHERE settlement_id = ? ORDER BY sequence DESC LIMIT 1
            """,
            (settlement_id,),
        ).fetchone()
        sequence = 1 if previous is None else int(previous["sequence"]) + 1
        previous_hash = _ZERO_HASH if previous is None else str(previous["event_hash"])
        event = {
            "type": "settlement_journal_entry",
            "protocol_version": PROTOCOL_VERSION,
            "settlement_id": settlement_id,
            "sequence": sequence,
            "state": state,
            "event_type": event_type,
            "payload": dict(payload),
            "previous_event_hash": previous_hash,
            "recorded_at": recorded_at,
        }
        event_hash = _canonical_hash(event)
        connection.execute(
            """
            INSERT INTO settlement_events (
                settlement_id, sequence, state, event_type, event_json,
                previous_event_hash, event_hash, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                settlement_id,
                sequence,
                state,
                event_type,
                _json(event),
                previous_hash,
                event_hash,
                recorded_at,
            ),
        )

    def _row_for_update(
        self,
        connection: sqlite3.Connection,
        settlement_id: str,
    ) -> sqlite3.Row:
        _identifier(settlement_id, "settlement_id")
        row = connection.execute(
            "SELECT * FROM settlements WHERE settlement_id = ?",
            (settlement_id,),
        ).fetchone()
        if row is None:
            _reject("settlement_not_found", "settlement_id", "unknown settlement")
        return row

    def _require_row(self, settlement_id: str) -> sqlite3.Row:
        _identifier(settlement_id, "settlement_id")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM settlements WHERE settlement_id = ?",
                (settlement_id,),
            ).fetchone()
        if row is None:
            _reject("settlement_not_found", "settlement_id", "unknown settlement")
        return row

    def _record_from_row(self, row: sqlite3.Row) -> SettlementRecord:
        receipt = self._receipt_from_row(row)
        submit_count = self.submit_intent_count(row["settlement_id"])
        return SettlementRecord(
            settlement_id=row["settlement_id"],
            request_hash=row["request_hash"],
            state=row["state"],
            submit_intent_count=submit_count,
            transaction_signature=row["transaction_signature"],
            reconciled_receipt=receipt,
        )

    def _receipt_from_row(
        self,
        row: sqlite3.Row,
    ) -> ReconciledSettlementReceipt | None:
        if row["reconciled_receipt_json"] is None:
            return None
        receipt = json.loads(row["reconciled_receipt_json"])
        supplied_hash = receipt.pop("receipt_hash")
        if _canonical_hash(receipt) != supplied_hash:
            _reject("receipt_tampering", "reconciled_receipt", "persisted hash mismatch")
        return self._receipt_dataclass({**receipt, "receipt_hash": supplied_hash})

    @staticmethod
    def _commitment_dataclass(
        value: Mapping[str, Any],
    ) -> SettlementExecutionCommitment:
        unsigned = {
            key: value[key]
            for key in (
                "settlement_request_hash",
                "execution_request_id",
                "execution_commitment_hash",
                "prepared_message_hash",
                "executor_id",
                "expected_signer",
                "expires_at",
            )
        }
        return SettlementExecutionCommitment(
            **unsigned,
            commitment_hash=_canonical_hash(value),
        )

    @staticmethod
    def _receipt_dataclass(
        value: Mapping[str, Any],
    ) -> ReconciledSettlementReceipt:
        return ReconciledSettlementReceipt(
            settlement_id=value["settlement_id"],
            settlement_request_hash=value["settlement_request_hash"],
            execution_request_id=value["execution_request_id"],
            obligation_id=value["obligation_id"],
            channel_id=value["channel_id"],
            channel_account=value["channel_account"],
            epoch=value["epoch"],
            mint=value["mint"],
            destination=value["destination"],
            requested_base_units=int(value["requested_base_units"]),
            settled_total_before=int(value["settled_total_before"]),
            settled_total_after=int(value["settled_total_after"]),
            vault_balance_before=int(value["vault_balance_before"]),
            vault_balance_after=int(value["vault_balance_after"]),
            transaction_signature=value["transaction_signature"],
            observation_hashes=tuple(value["observation_hashes"]),
            reconciliation_status=value["reconciliation_status"],
            completed_at=value["completed_at"],
            receipt_hash=value["receipt_hash"],
        )

    @staticmethod
    def _recovery_dataclass(value: Mapping[str, Any]) -> SettlementRecoveryRecord:
        return SettlementRecoveryRecord(
            settlement_id=value["settlement_id"],
            attempt=value["attempt"],
            outcome=value["outcome"],
            executor_id=value.get("executor_id"),
            status_response_hash=value.get("status_response_hash"),
            transaction_signature=value.get("transaction_signature"),
            submit_intent_count=value["submit_intent_count"],
            automatic_second_submission_count=value["automatic_second_submission_count"],
            observed_at=value["observed_at"],
            detail=value.get("detail"),
            recovery_hash=value["recovery_hash"],
        )
