"""Offline cumulative-voucher verification and a monotonic reference ledger."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import CanonicalizationError, canonical_json_bytes, sha256_raw_bytes

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PUBKEY = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SIGNATURE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,88}$")
_SUBMISSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_U64_MAX = 18_446_744_073_709_551_615
_JSON_SAFE_INTEGER_MAX = 9_007_199_254_740_991
_ZERO_HASH = "sha256:" + ("0" * 64)

_VOUCHER_FIELDS = frozenset(
    {"type", "protocol_version", "payload", "voucher_hash", "sender_signature"}
)
_PAYLOAD_FIELDS = frozenset(
    {
        "domain",
        "protocol_version",
        "environment",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "channel_account",
        "epoch",
        "sequence",
        "previous_activated_voucher_hash",
        "sender",
        "recipient_claim_pubkey",
        "mint",
        "cumulative_authorized_base_units",
        "issued_at",
        "expires_at",
    }
)
_LEDGER_STATES = frozenset({"issued", "verified", "activation_requested", "rejected"})

SignatureVerifier = Callable[[str, bytes, str], bool]


class VoucherValidationError(ValueError):
    """Stable fail-closed voucher or ledger rejection."""

    def __init__(self, code: str, field: str, detail: str) -> None:
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code}: {field}: {detail}")


def _reject(code: str, field: str, detail: str) -> None:
    raise VoucherValidationError(code, field, detail)


def _closed_object(value: object, *, field: str, required: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject("invalid_type", field, "expected an object")
    keys = set(value)
    missing = required - keys
    unknown = keys - required
    if missing:
        _reject("missing_field", field, f"missing {sorted(missing)}")
    if unknown:
        _reject("unknown_field", field, f"unknown {sorted(unknown)}")
    return value


def _literal(value: object, expected: object, field: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _reject("invalid_literal", field, f"expected {expected!r}")


def _integer(
    value: object,
    field: str,
    *,
    minimum: int = 0,
    maximum: int = _JSON_SAFE_INTEGER_MAX,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _reject("invalid_integer", field, f"expected integer in [{minimum}, {maximum}]")
    return value


def _string(value: object, field: str, pattern: re.Pattern[str], description: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _reject("invalid_string", field, description)
    return value


def _amount(value: object, field: str) -> int:
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        _reject("invalid_amount", field, "expected a canonical unsigned decimal")
    amount = int(value)
    if amount > _U64_MAX:
        _reject("amount_out_of_range", field, "expected an unsigned 64-bit integer")
    return amount


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        _reject("invalid_timestamp", field, "expected UTC seconds precision")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        _reject("invalid_timestamp", field, str(error))
    return parsed


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        _reject("invalid_clock", field, "expected a timezone-aware UTC datetime")
    return value.astimezone(timezone.utc)


def canonical_voucher_payload(payload: object) -> bytes:
    """Return RFC 8785 bytes after closed voucher-payload validation."""

    normalized = _closed_object(payload, field="payload", required=_PAYLOAD_FIELDS)
    if normalized["domain"] != "foundry.channels.voucher":
        _reject("domain_mismatch", "payload.domain", "unsupported signed-object domain")
    if normalized["protocol_version"] != "1.0.0":
        _reject(
            "protocol_version_unsupported",
            "payload.protocol_version",
            "unsupported voucher version",
        )
    if normalized["environment"] != "devnet":
        _reject("environment_mismatch", "payload.environment", "devnet MVP only")
    if normalized["network"] != "solana:devnet":
        _reject("network_mismatch", "payload.network", "devnet MVP only")
    for field in (
        "genesis_hash",
        "program_id",
        "channel_account",
        "sender",
        "recipient_claim_pubkey",
        "mint",
    ):
        _string(normalized[field], f"payload.{field}", _PUBKEY, "expected a base58 public key")
    _string(
        normalized["channel_id"],
        "payload.channel_id",
        _IDENTIFIER,
        "expected a protocol identifier",
    )
    _integer(normalized["epoch"], "payload.epoch")
    _integer(normalized["sequence"], "payload.sequence", minimum=1)
    _string(
        normalized["previous_activated_voucher_hash"],
        "payload.previous_activated_voucher_hash",
        _HASH,
        "expected sha256:<64 lowercase hex>",
    )
    _amount(
        normalized["cumulative_authorized_base_units"],
        "payload.cumulative_authorized_base_units",
    )
    issued = _timestamp(normalized["issued_at"], "payload.issued_at")
    expires = _timestamp(normalized["expires_at"], "payload.expires_at")
    if expires <= issued:
        _reject("voucher_time_order_invalid", "payload.expires_at", "must follow issued_at")
    try:
        return canonical_json_bytes(dict(normalized))
    except CanonicalizationError as error:
        _reject("canonicalization_failed", "payload", str(error))


def voucher_payload_hash(payload: object) -> str:
    """Hash exact canonical bytes; the closed payload domain separates the object."""

    return sha256_raw_bytes(canonical_voucher_payload(payload))


@dataclass(frozen=True)
class VoucherContext:
    """Authoritative caller-supplied snapshot used only for offline verification."""

    environment: str
    network: str
    genesis_hash: str
    program_id: str
    channel_id: str
    channel_account: str
    epoch: int
    sender: str
    recipient_claim_pubkey: str
    mint: str
    funded_total_base_units: int
    refunded_total_base_units: int
    policy_limit_base_units: int
    channel_expires_at: datetime
    latest_activated_sequence: int = 0
    latest_activated_total_base_units: int = 0
    latest_activated_voucher_hash: str = _ZERO_HASH

    def validate(self) -> None:
        if self.environment != "devnet" or self.network != "solana:devnet":
            _reject("invalid_context_domain", "context.network", "devnet MVP only")
        for field in (
            "genesis_hash",
            "program_id",
            "channel_account",
            "sender",
            "recipient_claim_pubkey",
            "mint",
        ):
            _string(getattr(self, field), f"context.{field}", _PUBKEY, "expected public key")
        _string(self.channel_id, "context.channel_id", _IDENTIFIER, "expected identifier")
        for field in (
            "funded_total_base_units",
            "refunded_total_base_units",
            "policy_limit_base_units",
            "latest_activated_total_base_units",
        ):
            value = getattr(self, field)
            if type(value) is not int or not 0 <= value <= _U64_MAX:
                _reject("invalid_context_amount", f"context.{field}", "expected u64 integer")
        for field in ("epoch", "latest_activated_sequence"):
            value = getattr(self, field)
            if type(value) is not int or not 0 <= value <= _JSON_SAFE_INTEGER_MAX:
                _reject(
                    "invalid_context_integer",
                    f"context.{field}",
                    "expected a JSON-safe unsigned integer",
                )
        if self.refunded_total_base_units > self.funded_total_base_units:
            _reject("invalid_context_accounting", "context.refunded_total_base_units", "R > F")
        capacity = self.funded_total_base_units - self.refunded_total_base_units
        if self.latest_activated_total_base_units > capacity:
            _reject("invalid_context_accounting", "context.latest_activated_total", "A > F - R")
        if self.latest_activated_total_base_units > self.policy_limit_base_units:
            _reject("invalid_context_accounting", "context.policy_limit", "A > policy")
        if (self.latest_activated_sequence == 0) != (self.latest_activated_total_base_units == 0):
            _reject(
                "invalid_context_accounting",
                "context.latest_activated_sequence",
                "sequence and total must both be zero or non-zero",
            )
        _string(
            self.latest_activated_voucher_hash,
            "context.latest_activated_voucher_hash",
            _HASH,
            "expected hash",
        )
        if self.latest_activated_sequence == 0:
            if self.latest_activated_voucher_hash != _ZERO_HASH:
                _reject(
                    "invalid_context_accounting",
                    "context.latest_activated_voucher_hash",
                    "zero activated state requires the zero hash",
                )
        elif self.latest_activated_voucher_hash == _ZERO_HASH:
            _reject(
                "invalid_context_accounting",
                "context.latest_activated_voucher_hash",
                "non-zero activated state requires a non-zero hash",
            )
        _utc(self.channel_expires_at, "context.channel_expires_at")


@dataclass(frozen=True)
class VerifiedVoucher:
    voucher_hash: str
    canonical_payload: bytes
    sequence: int
    cumulative_authorized_base_units: int
    expires_at: datetime


def verify_voucher(
    voucher: object,
    *,
    context: VoucherContext,
    now: datetime,
    signature_verifier: SignatureVerifier,
    latest_issued_sequence: int | None = None,
    latest_issued_total_base_units: int | None = None,
) -> VerifiedVoucher:
    """Verify one voucher without producing any authoritative activation state."""

    context.validate()
    checked_now = _utc(now, "now")
    envelope = _closed_object(voucher, field="voucher", required=_VOUCHER_FIELDS)
    _literal(envelope["type"], "channel_voucher", "voucher.type")
    _literal(envelope["protocol_version"], "1.0.0", "voucher.protocol_version")
    payload = _closed_object(envelope["payload"], field="payload", required=_PAYLOAD_FIELDS)
    canonical = canonical_voucher_payload(payload)
    expected_hash = sha256_raw_bytes(canonical)
    supplied_hash = _string(
        envelope["voucher_hash"],
        "voucher.voucher_hash",
        _HASH,
        "expected sha256:<64 lowercase hex>",
    )
    if supplied_hash != expected_hash:
        _reject("voucher_hash_mismatch", "voucher.voucher_hash", "does not bind payload")
    signature = _string(
        envelope["sender_signature"],
        "voucher.sender_signature",
        _SIGNATURE,
        "expected a public signature",
    )

    expected_fields = {
        "environment": context.environment,
        "network": context.network,
        "genesis_hash": context.genesis_hash,
        "program_id": context.program_id,
        "channel_id": context.channel_id,
        "channel_account": context.channel_account,
        "epoch": context.epoch,
        "sender": context.sender,
        "recipient_claim_pubkey": context.recipient_claim_pubkey,
        "mint": context.mint,
    }
    mismatch_codes = {
        "environment": "environment_mismatch",
        "network": "network_mismatch",
        "genesis_hash": "genesis_hash_mismatch",
        "program_id": "program_id_mismatch",
        "channel_id": "channel_mismatch",
        "channel_account": "channel_account_mismatch",
        "epoch": "epoch_mismatch",
        "sender": "sender_mismatch",
        "recipient_claim_pubkey": "recipient_mismatch",
        "mint": "mint_mismatch",
    }
    for field, expected in expected_fields.items():
        if payload[field] != expected:
            _reject(mismatch_codes[field], f"payload.{field}", "context mismatch")
    if payload["previous_activated_voucher_hash"] != context.latest_activated_voucher_hash:
        _reject(
            "previous_voucher_hash_mismatch",
            "payload.previous_activated_voucher_hash",
            "does not match authoritative activated snapshot",
        )

    sequence = _integer(payload["sequence"], "payload.sequence", minimum=1)
    total = _amount(
        payload["cumulative_authorized_base_units"],
        "payload.cumulative_authorized_base_units",
    )
    minimum_sequence = context.latest_activated_sequence
    minimum_total = context.latest_activated_total_base_units
    if latest_issued_sequence is not None:
        minimum_sequence = max(minimum_sequence, latest_issued_sequence)
    if latest_issued_total_base_units is not None:
        minimum_total = max(minimum_total, latest_issued_total_base_units)
    if sequence <= minimum_sequence:
        _reject("sequence_not_monotonic", "payload.sequence", "must be strictly increasing")
    if total < minimum_total:
        _reject(
            "cumulative_amount_decreased",
            "payload.cumulative_authorized_base_units",
            "must be nondecreasing",
        )
    if total == 0:
        _reject(
            "zero_cumulative_authorization",
            "payload.cumulative_authorized_base_units",
            "a sequenced voucher must authorize a positive cumulative total",
        )
    available = context.funded_total_base_units - context.refunded_total_base_units
    if total > available:
        _reject(
            "authorization_exceeds_funding",
            "payload.cumulative_authorized_base_units",
            "exceeds F - R",
        )
    if total > context.policy_limit_base_units:
        _reject(
            "authorization_exceeds_policy",
            "payload.cumulative_authorized_base_units",
            "exceeds policy limit",
        )
    issued = _timestamp(payload["issued_at"], "payload.issued_at")
    expires = _timestamp(payload["expires_at"], "payload.expires_at")
    if issued > checked_now:
        _reject("voucher_issued_in_future", "payload.issued_at", "issued_at exceeds verifier clock")
    if checked_now >= expires:
        _reject("voucher_expired", "payload.expires_at", "voucher is no longer valid")
    if expires > context.channel_expires_at:
        _reject("voucher_exceeds_channel_expiry", "payload.expires_at", "beyond channel expiry")
    try:
        signature_valid = signature_verifier(context.sender, canonical, signature)
    except Exception as error:
        _reject("signature_verifier_failed", "voucher.sender_signature", type(error).__name__)
    if signature_valid is not True:
        _reject("invalid_sender_signature", "voucher.sender_signature", "verification failed")
    return VerifiedVoucher(
        voucher_hash=expected_hash,
        canonical_payload=canonical,
        sequence=sequence,
        cumulative_authorized_base_units=total,
        expires_at=expires,
    )


@dataclass(frozen=True)
class VoucherRecord:
    submission_id: str
    state: str
    voucher_hash: str | None
    sequence: int | None
    cumulative_authorized_base_units: int | None
    error_code: str | None


class ReferenceVoucherLedger:
    """Durable monotonic journal of non-authoritative voucher processing states."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _connection(self) -> Any:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS voucher_submissions (
                    submission_id TEXT PRIMARY KEY,
                    voucher_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('issued', 'verified', 'activation_requested', 'rejected')
                    ),
                    voucher_hash TEXT,
                    domain_key TEXT,
                    channel_id TEXT,
                    epoch INTEGER,
                    sequence INTEGER,
                    cumulative_total TEXT,
                    expires_at TEXT,
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS voucher_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('issued', 'verified', 'activation_requested', 'rejected')
                    ),
                    error_code TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY (submission_id) REFERENCES voucher_submissions(submission_id)
                );
                CREATE INDEX IF NOT EXISTS idx_voucher_latest
                ON voucher_submissions(domain_key, sequence)
                WHERE state IN ('verified', 'activation_requested');
                """
            )

    @staticmethod
    def _domain_key(context: VoucherContext) -> str:
        identity = {
            "domain": "foundry.channels.voucher-ledger-scope",
            "protocol_version": "1.0.0",
            "environment": context.environment,
            "network": context.network,
            "genesis_hash": context.genesis_hash,
            "program_id": context.program_id,
            "channel_id": context.channel_id,
            "channel_account": context.channel_account,
            "epoch": context.epoch,
            "sender": context.sender,
            "recipient_claim_pubkey": context.recipient_claim_pubkey,
            "mint": context.mint,
        }
        return sha256_raw_bytes(canonical_json_bytes(identity)).removeprefix("sha256:")

    @staticmethod
    def _time(value: datetime) -> str:
        checked = _utc(value, "observed_at")
        return checked.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _record(row: sqlite3.Row) -> VoucherRecord:
        state = str(row["state"])
        if state not in _LEDGER_STATES:
            raise AssertionError(f"unexpected persisted state: {state}")
        return VoucherRecord(
            submission_id=str(row["submission_id"]),
            state=state,
            voucher_hash=row["voucher_hash"],
            sequence=row["sequence"],
            cumulative_authorized_base_units=(
                int(row["cumulative_total"]) if row["cumulative_total"] is not None else None
            ),
            error_code=row["error_code"],
        )

    def record_issued(
        self, submission_id: str, voucher: Mapping[str, Any], *, observed_at: datetime
    ) -> VoucherRecord:
        _string(submission_id, "submission_id", _SUBMISSION_ID, "expected identifier")
        if not isinstance(voucher, Mapping):
            _reject("invalid_type", "voucher", "expected object")
        try:
            serialized = json.dumps(
                dict(voucher),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as error:
            _reject("invalid_json", "voucher", str(error))
        timestamp = self._time(observed_at)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if existing is not None:
                if existing["voucher_json"] != serialized:
                    connection.rollback()
                    _reject(
                        "submission_id_collision",
                        "submission_id",
                        "identifier already binds different bytes",
                    )
                connection.commit()
                return self._record(existing)
            connection.execute(
                """
                INSERT INTO voucher_submissions (
                    submission_id, voucher_json, state, created_at, updated_at
                ) VALUES (?, ?, 'issued', ?, ?)
                """,
                (submission_id, serialized, timestamp, timestamp),
            )
            connection.execute(
                """
                INSERT INTO voucher_events (submission_id, state, observed_at)
                VALUES (?, 'issued', ?)
                """,
                (submission_id, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            connection.commit()
            assert row is not None
            return self._record(row)

    def verify_issued(
        self,
        submission_id: str,
        *,
        context: VoucherContext,
        now: datetime,
        signature_verifier: SignatureVerifier,
    ) -> VoucherRecord:
        timestamp = self._time(now)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                _reject("submission_not_found", "submission_id", "record issued first")
            assert row is not None
            if row["state"] in {"verified", "activation_requested"}:
                connection.commit()
                return self._record(row)
            if row["state"] == "rejected":
                connection.commit()
                _reject(
                    str(row["error_code"]),
                    "submission_id",
                    "submission was previously rejected",
                )
            voucher = json.loads(str(row["voucher_json"]))
            try:
                if _timestamp(row["updated_at"], "persisted.updated_at") > _utc(now, "now"):
                    _reject(
                        "journal_time_regressed",
                        "now",
                        "verification time precedes the latest journal event",
                    )
                context.validate()
                domain_key = self._domain_key(context)
                latest = connection.execute(
                    """
                    SELECT sequence, cumulative_total
                    FROM voucher_submissions
                    WHERE domain_key = ?
                      AND state IN ('verified', 'activation_requested')
                      AND submission_id != ?
                    ORDER BY sequence DESC
                    LIMIT 1
                    """,
                    (domain_key, submission_id),
                ).fetchone()
                verified = verify_voucher(
                    voucher,
                    context=context,
                    now=now,
                    signature_verifier=signature_verifier,
                    latest_issued_sequence=(int(latest["sequence"]) if latest else None),
                    latest_issued_total_base_units=(
                        int(latest["cumulative_total"]) if latest else None
                    ),
                )
            except VoucherValidationError as error:
                if error.code == "journal_time_regressed":
                    connection.rollback()
                    raise
                if error.code == "signature_verifier_failed":
                    connection.execute(
                        """
                        UPDATE voucher_submissions
                        SET state = 'issued', error_code = ?, updated_at = ?
                        WHERE submission_id = ?
                        """,
                        (error.code, timestamp, submission_id),
                    )
                    connection.execute(
                        """
                        INSERT INTO voucher_events (
                            submission_id, state, error_code, observed_at
                        ) VALUES (?, 'issued', ?, ?)
                        """,
                        (submission_id, error.code, timestamp),
                    )
                    connection.commit()
                    raise
                connection.execute(
                    """
                    UPDATE voucher_submissions
                    SET state = 'rejected', error_code = ?, updated_at = ?
                    WHERE submission_id = ?
                    """,
                    (error.code, timestamp, submission_id),
                )
                connection.execute(
                    """
                    INSERT INTO voucher_events (
                        submission_id, state, error_code, observed_at
                    ) VALUES (?, 'rejected', ?, ?)
                    """,
                    (submission_id, error.code, timestamp),
                )
                connection.commit()
                raise
            payload = voucher["payload"]
            connection.execute(
                """
                UPDATE voucher_submissions
                SET state = 'verified', voucher_hash = ?, domain_key = ?,
                    channel_id = ?, epoch = ?, sequence = ?, cumulative_total = ?,
                    expires_at = ?, error_code = NULL, updated_at = ?
                WHERE submission_id = ?
                """,
                (
                    verified.voucher_hash,
                    domain_key,
                    payload["channel_id"],
                    payload["epoch"],
                    verified.sequence,
                    str(verified.cumulative_authorized_base_units),
                    verified.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    timestamp,
                    submission_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO voucher_events (submission_id, state, observed_at)
                VALUES (?, 'verified', ?)
                """,
                (submission_id, timestamp),
            )
            updated = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            connection.commit()
            assert updated is not None
            return self._record(updated)

    def request_activation(
        self,
        submission_id: str,
        *,
        context: VoucherContext,
        observed_at: datetime,
        signature_verifier: SignatureVerifier,
    ) -> VoucherRecord:
        timestamp = self._time(observed_at)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                _reject("submission_not_found", "submission_id", "unknown submission")
            assert row is not None
            if row["state"] == "activation_requested":
                connection.commit()
                return self._record(row)
            if row["state"] != "verified":
                connection.rollback()
                _reject(
                    "activation_request_forbidden",
                    "state",
                    "only verified vouchers may request activation",
                )
            if _timestamp(row["updated_at"], "persisted.updated_at") > _utc(
                observed_at, "observed_at"
            ):
                connection.rollback()
                _reject(
                    "journal_time_regressed",
                    "observed_at",
                    "activation request precedes the latest journal event",
                )
            voucher = json.loads(str(row["voucher_json"]))
            try:
                context.validate()
                if self._domain_key(context) != row["domain_key"]:
                    _reject(
                        "activation_context_changed",
                        "context",
                        "current context does not match verified voucher domain",
                    )
                current = verify_voucher(
                    voucher,
                    context=context,
                    now=observed_at,
                    signature_verifier=signature_verifier,
                )
                if current.voucher_hash != row["voucher_hash"]:
                    _reject(
                        "persisted_voucher_mismatch",
                        "voucher_hash",
                        "verified record no longer matches persisted voucher",
                    )
            except VoucherValidationError as error:
                if error.code == "signature_verifier_failed":
                    connection.execute(
                        """
                        UPDATE voucher_submissions
                        SET state = 'verified', error_code = ?, updated_at = ?
                        WHERE submission_id = ?
                        """,
                        (error.code, timestamp, submission_id),
                    )
                    connection.execute(
                        """
                        INSERT INTO voucher_events (
                            submission_id, state, error_code, observed_at
                        ) VALUES (?, 'verified', ?, ?)
                        """,
                        (submission_id, error.code, timestamp),
                    )
                    connection.commit()
                    raise
                connection.execute(
                    """
                    UPDATE voucher_submissions
                    SET state = 'rejected', error_code = ?, updated_at = ?
                    WHERE submission_id = ?
                    """,
                    (error.code, timestamp, submission_id),
                )
                connection.execute(
                    """
                    INSERT INTO voucher_events (
                        submission_id, state, error_code, observed_at
                    ) VALUES (?, 'rejected', ?, ?)
                    """,
                    (submission_id, error.code, timestamp),
                )
                connection.commit()
                raise
            connection.execute(
                """
                UPDATE voucher_submissions
                SET state = 'activation_requested', error_code = NULL, updated_at = ?
                WHERE submission_id = ?
                """,
                (timestamp, submission_id),
            )
            connection.execute(
                """
                INSERT INTO voucher_events (submission_id, state, observed_at)
                VALUES (?, 'activation_requested', ?)
                """,
                (submission_id, timestamp),
            )
            updated = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            connection.commit()
            assert updated is not None
            return self._record(updated)

    def get(self, submission_id: str) -> VoucherRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM voucher_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
        if row is None:
            _reject("submission_not_found", "submission_id", "unknown submission")
        return self._record(row)

    def events(self, submission_id: str) -> list[dict[str, str | None]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT state, error_code, observed_at
                FROM voucher_events
                WHERE submission_id = ?
                ORDER BY event_id
                """,
                (submission_id,),
            ).fetchall()
        return [
            {
                "state": str(row["state"]),
                "error_code": row["error_code"],
                "observed_at": str(row["observed_at"]),
            }
            for row in rows
        ]
