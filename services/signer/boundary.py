"""Validate authorization and delegate signing of only its exact message bytes."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from foundry_external_execution_protocol import prepared_message_hash
from services.authorization import authorization_signing_payload

PROTOCOL_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {character: index for index, character in enumerate(_BASE58_ALPHABET)}
_AUTHORIZATION_FIELDS = {
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
_PREPARED_BINDING_FIELDS = {
    "type",
    "protocol_version",
    "execution_request_id",
    "economic_plan_hash",
    "prepared_message_base64",
    "prepared_message_hash",
    "execution_commitment_hash",
    "signer",
}


class SignerError(RuntimeError):
    """Base signer-boundary failure."""


class SignerInvalid(SignerError):
    """Authorization or exact-message binding is invalid."""


class SignerExpired(SignerError):
    """Authorization is outside its validity window."""


class SignerReplay(SignerError):
    """Authorization has already reached a terminal signing state."""


class SignerNeedsRecovery(SignerError):
    """The signing outcome is unknown and must be recovered manually."""


class AuthorizationSignatureVerifier(Protocol):
    """Verify Foundry authorization authenticity without holding its signing key."""

    def verify(self, payload: bytes, signature: str) -> bool: ...


class MessageSigningProvider(Protocol):
    """External HSM/MPC boundary; raw signing material never crosses this interface."""

    def sign_exact_message(self, message: bytes, *, expected_signer: str) -> str: ...


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise SignerInvalid(f"{path}: invalid UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise SignerInvalid(f"{path}: invalid UTC timestamp") from error


def _require_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise SignerInvalid(f"{path}: invalid identifier")
    return value


def _require_hash(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise SignerInvalid(f"{path}: invalid sha256 digest")
    return value


def _decode_base58(value: str, path: str) -> bytes:
    number = 0
    try:
        for character in value:
            number = number * 58 + _BASE58_INDEX[character]
    except KeyError as error:
        raise SignerInvalid(f"{path}: invalid base58") from error
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + payload


def _require_pubkey(value: Any, path: str) -> str:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        raise SignerInvalid(f"{path}: invalid Solana public key")
    if len(_decode_base58(value, path)) != 32:
        raise SignerInvalid(f"{path}: Solana public key must decode to 32 bytes")
    return value


def _require_closed(
    value: Any,
    fields: set[str],
    *,
    path: str,
    allow_additional: bool = False,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SignerInvalid(f"{path}: expected object")
    keys = set(value)
    missing = fields - keys
    unknown = keys - fields
    if missing:
        raise SignerInvalid(f"{path}: missing keys: {sorted(missing)}")
    if unknown and not allow_additional:
        raise SignerInvalid(f"{path}: unknown keys: {sorted(unknown)}")
    return value


def _decode_canonical_base64(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise SignerInvalid("$prepared_execution.prepared_message_base64: expected string")
    try:
        message = base64.b64decode(value, validate=True)
    except (TypeError, ValueError) as error:
        raise SignerInvalid("prepared message is not canonical base64") from error
    if not message or base64.b64encode(message).decode("ascii") != value:
        raise SignerInvalid("prepared message is not canonical base64")
    return message


class SignerJournal:
    """Durable, signer-local single-use journal."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signer_operations (
                    authorization_id TEXT PRIMARY KEY,
                    execution_request_id TEXT NOT NULL,
                    prepared_message_hash TEXT NOT NULL,
                    signer TEXT NOT NULL,
                    state TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    completed_at TEXT,
                    signature_envelope TEXT,
                    receipt_json TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def claim(
        self,
        *,
        authorization_id: str,
        execution_request_id: str,
        message_hash: str,
        signer: str,
        now: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT state, execution_request_id, prepared_message_hash, signer
                FROM signer_operations
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["execution_request_id"] != execution_request_id
                    or existing["prepared_message_hash"] != message_hash
                    or existing["signer"] != signer
                ):
                    raise SignerInvalid(
                        "authorization_id was rebound to different immutable inputs"
                    )
                if existing["state"] in {"signing", "needs_recovery"}:
                    raise SignerNeedsRecovery(authorization_id)
                raise SignerReplay(authorization_id)
            connection.execute(
                """
                INSERT INTO signer_operations (
                    authorization_id,
                    execution_request_id,
                    prepared_message_hash,
                    signer,
                    state,
                    claimed_at
                ) VALUES (?, ?, ?, ?, 'signing', ?)
                """,
                (
                    authorization_id,
                    execution_request_id,
                    message_hash,
                    signer,
                    _format_timestamp(now),
                ),
            )

    def complete(
        self,
        authorization_id: str,
        *,
        signature_envelope: str,
        receipt: Mapping[str, Any],
        now: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = connection.execute(
                """
                UPDATE signer_operations
                SET state = 'signed',
                    completed_at = ?,
                    signature_envelope = ?,
                    receipt_json = ?
                WHERE authorization_id = ? AND state = 'signing'
                """,
                (
                    _format_timestamp(now),
                    signature_envelope,
                    json.dumps(receipt, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    authorization_id,
                ),
            )
            if result.rowcount != 1:
                raise SignerNeedsRecovery(authorization_id)

    def mark_needs_recovery(self, authorization_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE signer_operations
                SET state = 'needs_recovery'
                WHERE authorization_id = ? AND state = 'signing'
                """,
                (authorization_id,),
            )

    def status(self, authorization_id: str) -> dict[str, Any]:
        _require_identifier(authorization_id, "$authorization_id")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM signer_operations
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
        if row is None:
            raise SignerInvalid("authorization was not presented to signer")
        return {
            "authorization_id": row["authorization_id"],
            "execution_request_id": row["execution_request_id"],
            "prepared_message_hash": row["prepared_message_hash"],
            "signer": row["signer"],
            "state": row["state"],
            "claimed_at": row["claimed_at"],
            "completed_at": row["completed_at"],
            "signature_envelope": row["signature_envelope"],
            "receipt": json.loads(row["receipt_json"]) if row["receipt_json"] else None,
        }


class ExactMessageSigner:
    """Verify a Foundry grant, then sign only its exact prepared message bytes."""

    def __init__(
        self,
        journal: SignerJournal,
        *,
        authorization_verifier: AuthorizationSignatureVerifier,
        signing_provider: MessageSigningProvider,
        signer_id: str,
    ):
        self.journal = journal
        self.authorization_verifier = authorization_verifier
        self.signing_provider = signing_provider
        self.signer_id = _require_pubkey(signer_id, "$signer_id")

    def sign(
        self,
        *,
        prepared_execution: Mapping[str, Any],
        authorization: Mapping[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        current = now.astimezone(UTC).replace(microsecond=0)
        authorized = _require_closed(
            authorization,
            _AUTHORIZATION_FIELDS,
            path="$authorization",
        )
        if authorized["type"] != "execution_authorization":
            raise SignerInvalid("unsupported authorization type")
        if authorized["protocol_version"] != PROTOCOL_VERSION:
            raise SignerInvalid("unsupported authorization version")
        authorization_id = _require_identifier(
            authorized["authorization_id"],
            "$authorization.authorization_id",
        )
        request_id = _require_identifier(
            authorized["execution_request_id"],
            "$authorization.execution_request_id",
        )
        commitment_hash = _require_hash(
            authorized["execution_commitment_hash"],
            "$authorization.execution_commitment_hash",
        )
        message_hash = _require_hash(
            authorized["prepared_message_hash"],
            "$authorization.prepared_message_hash",
        )
        signer = _require_pubkey(authorized["signer"], "$authorization.signer")
        if signer != self.signer_id:
            raise SignerInvalid("authorization targets a different signer")
        if authorized["single_use"] is not True:
            raise SignerInvalid("authorization must be single-use")
        issued_at = _parse_timestamp(authorized["issued_at"], "$authorization.issued_at")
        expires_at = _parse_timestamp(authorized["expires_at"], "$authorization.expires_at")
        if issued_at > current:
            raise SignerInvalid("authorization was issued in the future")
        if expires_at <= current:
            raise SignerExpired(authorization_id)
        signature = authorized["authorization_signature"]
        if not isinstance(signature, str) or not signature:
            raise SignerInvalid("authorization signature is missing")
        try:
            authentic = self.authorization_verifier.verify(
                authorization_signing_payload(authorized),
                signature,
            )
        except Exception as error:
            raise SignerInvalid("authorization signature verification failed") from error
        if authentic is not True:
            raise SignerInvalid("authorization signature verification failed")

        prepared = _require_closed(
            prepared_execution,
            _PREPARED_BINDING_FIELDS,
            path="$prepared_execution",
            allow_additional=True,
        )
        if prepared["type"] != "prepared_execution":
            raise SignerInvalid("unsupported prepared execution type")
        if prepared["protocol_version"] != PROTOCOL_VERSION:
            raise SignerInvalid("unsupported prepared execution version")
        if prepared["execution_request_id"] != request_id:
            raise SignerInvalid("execution_request_id binding mismatch")
        if prepared["execution_commitment_hash"] != commitment_hash:
            raise SignerInvalid("execution_commitment_hash binding mismatch")
        if prepared["prepared_message_hash"] != message_hash:
            raise SignerInvalid("prepared_message_hash binding mismatch")
        if prepared["signer"] != signer:
            raise SignerInvalid("signer binding mismatch")

        message = _decode_canonical_base64(prepared["prepared_message_base64"])
        if prepared_message_hash(message) != message_hash:
            raise SignerInvalid("exact prepared message bytes are not authorized")

        self.journal.claim(
            authorization_id=authorization_id,
            execution_request_id=request_id,
            message_hash=message_hash,
            signer=signer,
            now=current,
        )
        try:
            signature_envelope = self.signing_provider.sign_exact_message(
                message,
                expected_signer=signer,
            )
            if not isinstance(signature_envelope, str) or not signature_envelope:
                raise RuntimeError("signing provider returned an invalid envelope")
            receipt = {
                "type": "message_signature_receipt",
                "protocol_version": PROTOCOL_VERSION,
                "authorization_id": authorization_id,
                "execution_request_id": request_id,
                "execution_commitment_hash": commitment_hash,
                "prepared_message_hash": message_hash,
                "signer": signer,
                "signature_envelope": signature_envelope,
                "signed_at": _format_timestamp(current),
            }
            self.journal.complete(
                authorization_id,
                signature_envelope=signature_envelope,
                receipt=receipt,
                now=current,
            )
        except Exception as error:
            self.journal.mark_needs_recovery(authorization_id)
            raise SignerNeedsRecovery(authorization_id) from error
        return receipt
