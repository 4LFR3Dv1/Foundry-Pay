"""Offline ChannelClaim and initial RecipientBinding verification.

The verifier deliberately accepts no locator and no Cloud-selected destination.
The destination authority is the exact wallet inside the payload co-signed by
the claim key and that destination wallet.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, NoReturn, Protocol

from .canonical import CanonicalizationError, canonical_json_bytes, sha256_raw_bytes

_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PUBKEY = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SIGNATURE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,88}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_JSON_SAFE_UNSIGNED_MAX = 9_007_199_254_740_991
_U64_MAX = 18_446_744_073_709_551_615

_CLAIM_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "claim_id",
        "channel_id",
        "channel_account",
        "epoch",
        "locator_hash",
        "claim_pubkey",
        "voucher_hash",
        "cumulative_authorized_base_units",
        "state",
        "created_at",
        "expires_at",
    }
)
_BINDING_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "payload",
        "binding_hash",
        "claim_key_signature",
        "destination_wallet_signature",
    }
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
        "claim_id",
        "claim_pubkey",
        "voucher_hash",
        "mint",
        "binding_mode",
        "destination_wallet",
        "binding_nonce",
        "issued_at",
        "expires_at",
    }
)
_CLAIM_STATES = frozenset(
    {
        "created",
        "delivered",
        "opened",
        "identity_verified",
        "destination_bound",
        "settlement_ready",
        "settled",
        "expired",
        "revoked",
        "blocked",
        "already_claimed",
    }
)
_BINDABLE_CLAIM_STATES = frozenset({"created", "delivered", "opened", "identity_verified"})


class RecipientBindingValidationError(ValueError):
    """Stable, fail-closed claim or binding rejection."""

    def __init__(self, code: str, field: str, detail: str) -> None:
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code} at {field}: {detail}")


class SignatureVerifier(Protocol):
    """Injected cryptographic verifier; production keys never enter this module."""

    def verify(self, public_key: str, payload: bytes, signature: str) -> bool:
        """Return true only when signature authenticates the exact payload bytes."""


@dataclass(frozen=True, slots=True)
class RecipientBindingContext:
    """Authoritative context supplied independently of locator or Cloud state."""

    environment: str
    network: str
    genesis_hash: str
    program_id: str
    channel_id: str
    channel_account: str
    epoch: int
    claim_id: str
    claim_pubkey: str
    voucher_hash: str
    mint: str


@dataclass(frozen=True, slots=True)
class VerifiedRecipientBinding:
    """A locally verified binding, not an on-chain activation declaration."""

    journal_domain_hash: str
    environment: str
    network: str
    genesis_hash: str
    program_id: str
    channel_id: str
    channel_account: str
    epoch: int
    claim_id: str
    claim_pubkey: str
    voucher_hash: str
    mint: str
    destination_wallet: str
    binding_nonce: int
    binding_hash: str
    verified_at: str
    state: str = "verified"

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _reject(code: str, field: str, detail: str) -> NoReturn:
    raise RecipientBindingValidationError(code, field, detail)


def _closed(
    value: object,
    *,
    field: str,
    required: frozenset[str],
    allowed: frozenset[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject("invalid_type", field, "expected an object")
    keys = set(value)
    missing = sorted(str(item) for item in required - keys)
    unknown = sorted(str(item) for item in keys - allowed)
    if missing:
        _reject("missing_field", field, f"missing {', '.join(missing)}")
    if unknown:
        _reject("unknown_field", field, f"unknown {', '.join(unknown)}")
    return value


def _literal(value: object, expected: object, field: str) -> None:
    if value != expected or type(value) is not type(expected):
        _reject("invalid_literal", field, f"expected {expected!r}")


def _string(value: object, pattern: re.Pattern[str], field: str, code: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _reject(code, field, "invalid canonical representation")
    return value


def _identifier(value: object, field: str) -> str:
    return _string(value, _IDENTIFIER, field, "invalid_identifier")


def _pubkey(value: object, field: str) -> str:
    return _string(value, _PUBKEY, field, "invalid_pubkey")


def _hash(value: object, field: str) -> str:
    return _string(value, _HASH, field, "invalid_hash")


def _signature(value: object, field: str) -> str:
    return _string(value, _SIGNATURE, field, "invalid_signature")


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > _JSON_SAFE_UNSIGNED_MAX:
        _reject(
            "invalid_integer",
            field,
            f"expected JSON-safe integer {minimum}..{_JSON_SAFE_UNSIGNED_MAX}",
        )
    return value


def _amount(value: object, field: str) -> int:
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        _reject("invalid_amount", field, "expected an unsigned canonical decimal string")
    amount = int(value)
    if amount > _U64_MAX:
        _reject("amount_out_of_range", field, "expected an unsigned 64-bit integer")
    return amount


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        _reject("invalid_timestamp", field, "expected UTC seconds in YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject("invalid_timestamp", field, "timestamp is not a real calendar time")
    return parsed


def _now(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        _reject("invalid_now", "now", "expected a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _matches(actual: object, expected: object, field: str) -> None:
    if actual != expected or type(actual) is not type(expected):
        _reject("context_mismatch", field, "does not match authoritative context")


def _validate_context(context: RecipientBindingContext) -> None:
    _literal(context.environment, "devnet", "context.environment")
    _literal(context.network, "solana:devnet", "context.network")
    _pubkey(context.genesis_hash, "context.genesis_hash")
    _pubkey(context.program_id, "context.program_id")
    _identifier(context.channel_id, "context.channel_id")
    _pubkey(context.channel_account, "context.channel_account")
    _integer(context.epoch, "context.epoch")
    _identifier(context.claim_id, "context.claim_id")
    _pubkey(context.claim_pubkey, "context.claim_pubkey")
    _hash(context.voucher_hash, "context.voucher_hash")
    _pubkey(context.mint, "context.mint")


def recipient_binding_domain_hash(context: RecipientBindingContext) -> str:
    """Hash the complete authority domain used to scope one-use persistence."""

    _validate_context(context)
    domain = {
        "domain": "foundry.channels.recipient-binding-journal",
        "protocol_version": "1.0.0",
        "environment": context.environment,
        "network": context.network,
        "genesis_hash": context.genesis_hash,
        "program_id": context.program_id,
        "channel_id": context.channel_id,
        "channel_account": context.channel_account,
        "epoch": context.epoch,
        "claim_id": context.claim_id,
        "claim_pubkey": context.claim_pubkey,
        "voucher_hash": context.voucher_hash,
        "mint": context.mint,
    }
    try:
        canonical = canonical_json_bytes(domain)
    except CanonicalizationError as error:
        _reject("canonicalization_failed", "context", str(error))
    return sha256_raw_bytes(canonical)


def validate_channel_claim(
    claim_value: object,
    *,
    context: RecipientBindingContext,
    now: datetime,
) -> Mapping[str, Any]:
    """Validate a non-authoritative claim reference against trusted context."""

    _validate_context(context)
    claim = _closed(
        claim_value,
        field="claim",
        required=_CLAIM_FIELDS,
        allowed=_CLAIM_FIELDS,
    )
    _literal(claim["type"], "channel_claim", "claim.type")
    _literal(claim["protocol_version"], "1.0.0", "claim.protocol_version")
    _identifier(claim["claim_id"], "claim.claim_id")
    _identifier(claim["channel_id"], "claim.channel_id")
    _pubkey(claim["channel_account"], "claim.channel_account")
    _integer(claim["epoch"], "claim.epoch")
    _hash(claim["locator_hash"], "claim.locator_hash")
    _pubkey(claim["claim_pubkey"], "claim.claim_pubkey")
    _hash(claim["voucher_hash"], "claim.voucher_hash")
    _amount(claim["cumulative_authorized_base_units"], "claim.cumulative_authorized_base_units")
    if claim["state"] not in _CLAIM_STATES:
        _reject("invalid_claim_state", "claim.state", "unsupported state")
    created_at = _timestamp(claim["created_at"], "claim.created_at")
    expires_at = _timestamp(claim["expires_at"], "claim.expires_at")
    if expires_at <= created_at:
        _reject("invalid_claim_window", "claim.expires_at", "must be after created_at")
    current_time = _now(now)
    if current_time < created_at:
        _reject("claim_not_yet_valid", "claim.created_at", "claim is not active yet")
    if current_time >= expires_at:
        _reject("claim_expired", "claim.expires_at", "claim is no longer bindable")
    if claim["state"] not in _BINDABLE_CLAIM_STATES:
        _reject("claim_not_bindable", "claim.state", "state cannot accept initial binding")

    for field in (
        "claim_id",
        "channel_id",
        "channel_account",
        "epoch",
        "claim_pubkey",
        "voucher_hash",
    ):
        _matches(claim[field], getattr(context, field), f"claim.{field}")
    return claim


def canonical_recipient_binding_payload(
    binding_value: object,
    *,
    context: RecipientBindingContext,
    claim: Mapping[str, Any],
    now: datetime,
) -> bytes:
    """Return the one exact RFC 8785 payload both principals must sign."""

    binding = _closed(
        binding_value,
        field="binding",
        required=_BINDING_FIELDS,
        allowed=_BINDING_FIELDS,
    )
    _literal(binding["type"], "recipient_binding", "binding.type")
    _literal(binding["protocol_version"], "1.0.0", "binding.protocol_version")
    payload = _closed(
        binding["payload"],
        field="binding.payload",
        required=_PAYLOAD_FIELDS,
        allowed=_PAYLOAD_FIELDS,
    )
    _literal(payload["domain"], "foundry.channels.recipient-binding", "binding.payload.domain")
    _literal(payload["protocol_version"], "1.0.0", "binding.payload.protocol_version")
    _literal(payload["environment"], "devnet", "binding.payload.environment")
    _literal(payload["network"], "solana:devnet", "binding.payload.network")
    _pubkey(payload["genesis_hash"], "binding.payload.genesis_hash")
    _pubkey(payload["program_id"], "binding.payload.program_id")
    _identifier(payload["channel_id"], "binding.payload.channel_id")
    _pubkey(payload["channel_account"], "binding.payload.channel_account")
    _integer(payload["epoch"], "binding.payload.epoch")
    _identifier(payload["claim_id"], "binding.payload.claim_id")
    _pubkey(payload["claim_pubkey"], "binding.payload.claim_pubkey")
    _hash(payload["voucher_hash"], "binding.payload.voucher_hash")
    _pubkey(payload["mint"], "binding.payload.mint")
    _literal(payload["binding_mode"], "initial", "binding.payload.binding_mode")
    _pubkey(payload["destination_wallet"], "binding.payload.destination_wallet")
    _integer(payload["binding_nonce"], "binding.payload.binding_nonce", minimum=1)
    issued_at = _timestamp(payload["issued_at"], "binding.payload.issued_at")
    expires_at = _timestamp(payload["expires_at"], "binding.payload.expires_at")
    if expires_at <= issued_at:
        _reject("invalid_binding_window", "binding.payload.expires_at", "must be after issued_at")
    if _now(now) < issued_at:
        _reject("binding_not_yet_valid", "binding.payload.issued_at", "issued in the future")
    if _now(now) >= expires_at:
        _reject("binding_expired", "binding.payload.expires_at", "binding is no longer valid")
    claim_created_at = _timestamp(claim["created_at"], "claim.created_at")
    claim_expires_at = _timestamp(claim["expires_at"], "claim.expires_at")
    if issued_at < claim_created_at:
        _reject("binding_predates_claim", "binding.payload.issued_at", "precedes claim creation")
    if expires_at > claim_expires_at:
        _reject("binding_outlives_claim", "binding.payload.expires_at", "exceeds claim expiry")

    try:
        return canonical_json_bytes(dict(payload))
    except CanonicalizationError as error:
        _reject("canonicalization_failed", "binding.payload", str(error))


def verify_recipient_binding(
    claim_value: object,
    binding_value: object,
    *,
    context: RecipientBindingContext,
    signature_verifier: SignatureVerifier,
    now: datetime,
) -> VerifiedRecipientBinding:
    """Verify initial binding, including two signatures over identical bytes."""

    claim = validate_channel_claim(claim_value, context=context, now=now)
    binding = _closed(
        binding_value,
        field="binding",
        required=_BINDING_FIELDS,
        allowed=_BINDING_FIELDS,
    )
    payload_bytes = canonical_recipient_binding_payload(
        binding,
        context=context,
        claim=claim,
        now=now,
    )
    expected_hash = sha256_raw_bytes(payload_bytes)
    _hash(binding["binding_hash"], "binding.binding_hash")
    if binding["binding_hash"] != expected_hash:
        _reject("binding_hash_mismatch", "binding.binding_hash", "does not hash canonical payload")

    payload = binding["payload"]
    for field in (
        "environment",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "channel_account",
        "epoch",
        "claim_id",
        "claim_pubkey",
        "voucher_hash",
        "mint",
    ):
        _matches(payload[field], getattr(context, field), f"binding.payload.{field}")

    claim_signature = _signature(binding["claim_key_signature"], "binding.claim_key_signature")
    wallet_signature = _signature(
        binding["destination_wallet_signature"],
        "binding.destination_wallet_signature",
    )
    try:
        claim_valid = signature_verifier.verify(
            context.claim_pubkey,
            payload_bytes,
            claim_signature,
        )
    except Exception as error:
        _reject("signature_verifier_failed", "binding.claim_key_signature", type(error).__name__)
    if claim_valid is not True:
        _reject("invalid_claim_signature", "binding.claim_key_signature", "verification failed")
    try:
        wallet_valid = signature_verifier.verify(
            payload["destination_wallet"],
            payload_bytes,
            wallet_signature,
        )
    except Exception as error:
        _reject(
            "signature_verifier_failed",
            "binding.destination_wallet_signature",
            type(error).__name__,
        )
    if wallet_valid is not True:
        _reject(
            "invalid_destination_signature",
            "binding.destination_wallet_signature",
            "verification failed",
        )

    verified_at = _now(now).strftime("%Y-%m-%dT%H:%M:%SZ")
    return VerifiedRecipientBinding(
        journal_domain_hash=recipient_binding_domain_hash(context),
        environment=context.environment,
        network=context.network,
        genesis_hash=context.genesis_hash,
        program_id=context.program_id,
        channel_id=context.channel_id,
        channel_account=context.channel_account,
        epoch=context.epoch,
        claim_id=context.claim_id,
        claim_pubkey=context.claim_pubkey,
        voucher_hash=context.voucher_hash,
        mint=context.mint,
        destination_wallet=payload["destination_wallet"],
        binding_nonce=payload["binding_nonce"],
        binding_hash=expected_hash,
        verified_at=verified_at,
    )


class RecipientBindingLedger:
    """SQLite one-use initial-binding journal with restart-safe atomic insert."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 30000")
        except Exception:
            connection.close()
            raise
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recipient_bindings (
                    journal_domain_hash TEXT NOT NULL PRIMARY KEY,
                    environment TEXT NOT NULL,
                    network TEXT NOT NULL,
                    genesis_hash TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_account TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    claim_id TEXT NOT NULL,
                    claim_pubkey TEXT NOT NULL,
                    voucher_hash TEXT NOT NULL,
                    mint TEXT NOT NULL,
                    destination_wallet TEXT NOT NULL,
                    binding_nonce INTEGER NOT NULL,
                    binding_hash TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state = 'verified'),
                    UNIQUE (binding_hash)
                )
                """
            )
            connection.commit()

    def verify_and_record(
        self,
        claim_value: object,
        binding_value: object,
        *,
        context: RecipientBindingContext,
        signature_verifier: SignatureVerifier,
        now: datetime,
    ) -> VerifiedRecipientBinding:
        """Verify then atomically consume the claim's one allowed initial binding."""

        result = verify_recipient_binding(
            claim_value,
            binding_value,
            context=context,
            signature_verifier=signature_verifier,
            now=now,
        )
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT binding_hash, binding_nonce
                    FROM recipient_bindings
                    WHERE journal_domain_hash = ?
                    """,
                    (result.journal_domain_hash,),
                ).fetchone()
                if existing is not None:
                    _reject(
                        "binding_already_recorded",
                        "binding.payload.binding_nonce",
                        "initial binding is one-use; rebind is disabled",
                    )
                connection.execute(
                    """
                    INSERT INTO recipient_bindings (
                        journal_domain_hash, environment, network, genesis_hash, program_id,
                        channel_id, channel_account, epoch, claim_id, claim_pubkey,
                        voucher_hash, mint, destination_wallet, binding_nonce, binding_hash,
                        verified_at, state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.journal_domain_hash,
                        result.environment,
                        result.network,
                        result.genesis_hash,
                        result.program_id,
                        result.channel_id,
                        result.channel_account,
                        result.epoch,
                        result.claim_id,
                        result.claim_pubkey,
                        result.voucher_hash,
                        result.mint,
                        result.destination_wallet,
                        result.binding_nonce,
                        result.binding_hash,
                        result.verified_at,
                        result.state,
                    ),
                )
                connection.commit()
            except RecipientBindingValidationError:
                connection.rollback()
                raise
            except sqlite3.IntegrityError:
                connection.rollback()
                _reject(
                    "binding_replay",
                    "binding.binding_hash",
                    "binding or nonce has already been consumed",
                )
        return result

    def get(
        self,
        *,
        context: RecipientBindingContext,
    ) -> VerifiedRecipientBinding | None:
        """Read a persisted verified record; no activation state is inferred."""

        domain_hash = recipient_binding_domain_hash(context)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT journal_domain_hash, environment, network, genesis_hash, program_id,
                       channel_id, channel_account, epoch, claim_id, claim_pubkey,
                       voucher_hash, mint, destination_wallet, binding_nonce, binding_hash,
                       verified_at, state
                FROM recipient_bindings
                WHERE journal_domain_hash = ?
                """,
                (domain_hash,),
            ).fetchone()
        if row is None:
            return None
        return VerifiedRecipientBinding(**dict(row))
