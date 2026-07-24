"""Fail-closed Channel and ChannelFunding validation.

This module is deliberately offline. It validates a caller-provided snapshot;
it does not assert that the snapshot came from Solana or replace independent
on-chain observation.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, NoReturn


_AMOUNT = re.compile(r"^(0|[1-9][0-9]*)$")
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PUBKEY = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SIGNATURE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,88}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_CHANNEL_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "account_version",
        "environment",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "channel_account",
        "epoch",
        "sender",
        "recipient_claim_pubkey",
        "recipient_wallet",
        "mint",
        "decimals",
        "vault_token_account",
        "funded_total_base_units",
        "activated_authorized_total_base_units",
        "settled_total_base_units",
        "refunded_total_base_units",
        "latest_activated_sequence",
        "latest_activated_voucher_hash",
        "status",
        "expires_at",
        "close_requested_at",
        "claim_deadline",
        "policy",
        "created_at",
        "updated_at",
    }
)
_CHANNEL_REQUIRED = _CHANNEL_FIELDS - {
    "recipient_wallet",
    "close_requested_at",
    "claim_deadline",
}
_FUNDING_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "funding_id",
        "channel_id",
        "channel_account",
        "mint",
        "amount_base_units",
        "funded_total_after_base_units",
        "transaction_signature",
        "observed_slot",
        "observed_at",
    }
)
_POLICY_FIELDS = frozenset(
    {
        "type",
        "protocol_version",
        "channel_id",
        "max_cumulative_authorized_base_units",
        "allow_partial_settlement",
        "allow_top_up",
        "minimum_close_grace_seconds",
        "rebind_mode",
    }
)
_CLOSING_STATUSES = frozenset({"closing"})
_NON_CLOSING_STATUSES = frozenset(
    {
        "draft",
        "funding",
        "active",
        "settling",
        "closed",
        "expired",
        "blocked",
        "disputed",
        "needs_recovery",
        "needs_review",
    }
)


class ChannelValidationError(ValueError):
    """A stable, fail-closed validation failure."""

    def __init__(self, code: str, field: str, detail: str) -> None:
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code} at {field}: {detail}")


@dataclass(frozen=True, slots=True)
class AccountingProjection:
    """Derived accounting values for a validated channel snapshot."""

    funded_total_base_units: int
    activated_authorized_total_base_units: int
    settled_total_base_units: int
    refunded_total_base_units: int
    vault_balance_base_units: int
    outstanding_right_base_units: int
    unallocated_capacity_base_units: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _reject(code: str, field: str, detail: str) -> NoReturn:
    raise ChannelValidationError(code, field, detail)


def _closed_object(
    value: object, *, field: str, required: frozenset[str], allowed: frozenset[str]
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


def _integer(value: object, *, field: str, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int:
        _reject("invalid_integer", field, "expected an integer")
    if value < minimum or (maximum is not None and value > maximum):
        _reject("integer_out_of_range", field, f"expected {minimum}..{maximum or 'unbounded'}")
    return value


def _amount(value: object, field: str) -> int:
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        _reject("invalid_amount", field, "expected an unsigned canonical decimal string")
    return int(value)


def _pubkey(value: object, field: str) -> str:
    if not isinstance(value, str) or _PUBKEY.fullmatch(value) is None:
        _reject("invalid_pubkey", field, "expected a base58 public identifier")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _reject("invalid_identifier", field, "expected a closed protocol identifier")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        _reject("invalid_timestamp", field, "expected UTC seconds in YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject("invalid_timestamp", field, "timestamp is not a real calendar time")


def _validate_policy(value: object, channel_id: str) -> int:
    policy = _closed_object(
        value,
        field="policy",
        required=_POLICY_FIELDS,
        allowed=_POLICY_FIELDS,
    )
    _literal(policy["type"], "channel_policy", "policy.type")
    _literal(policy["protocol_version"], "1.0.0", "policy.protocol_version")
    if policy["channel_id"] != channel_id:
        _reject("policy_channel_mismatch", "policy.channel_id", "must equal channel_id")
    limit = _amount(
        policy["max_cumulative_authorized_base_units"],
        "policy.max_cumulative_authorized_base_units",
    )
    _literal(policy["allow_partial_settlement"], True, "policy.allow_partial_settlement")
    _literal(policy["allow_top_up"], True, "policy.allow_top_up")
    _integer(
        policy["minimum_close_grace_seconds"],
        field="policy.minimum_close_grace_seconds",
        minimum=1,
        maximum=31_536_000,
    )
    if policy["rebind_mode"] not in {"disabled", "current_and_new_wallet"}:
        _reject("invalid_rebind_mode", "policy.rebind_mode", "unsupported mode")
    return limit


def validate_channel(value: object) -> AccountingProjection:
    """Validate a closed Channel v1 snapshot and derive conservation values."""

    channel = _closed_object(
        value,
        field="channel",
        required=_CHANNEL_REQUIRED,
        allowed=_CHANNEL_FIELDS,
    )
    _literal(channel["type"], "channel", "type")
    _literal(channel["protocol_version"], "1.0.0", "protocol_version")
    _literal(channel["account_version"], 1, "account_version")
    _literal(channel["environment"], "devnet", "environment")
    _literal(channel["network"], "solana:devnet", "network")
    for field in (
        "genesis_hash",
        "program_id",
        "channel_account",
        "sender",
        "recipient_claim_pubkey",
        "mint",
        "vault_token_account",
    ):
        _pubkey(channel[field], field)
    if "recipient_wallet" in channel:
        _pubkey(channel["recipient_wallet"], "recipient_wallet")
    channel_id = _identifier(channel["channel_id"], "channel_id")
    _integer(channel["epoch"], field="epoch")
    _integer(channel["decimals"], field="decimals", maximum=18)
    sequence = _integer(channel["latest_activated_sequence"], field="latest_activated_sequence")
    latest_hash = channel["latest_activated_voucher_hash"]
    if not isinstance(latest_hash, str) or _HASH.fullmatch(latest_hash) is None:
        _reject(
            "invalid_hash", "latest_activated_voucher_hash", "expected sha256:<64 lowercase hex>"
        )

    funded = _amount(channel["funded_total_base_units"], "funded_total_base_units")
    activated = _amount(
        channel["activated_authorized_total_base_units"],
        "activated_authorized_total_base_units",
    )
    settled = _amount(channel["settled_total_base_units"], "settled_total_base_units")
    refunded = _amount(channel["refunded_total_base_units"], "refunded_total_base_units")
    policy_limit = _validate_policy(channel["policy"], channel_id)

    if refunded > funded:
        _reject("refund_exceeds_funding", "refunded_total_base_units", "R must be <= F")
    if activated > funded - refunded:
        _reject(
            "authorization_exceeds_capacity",
            "activated_authorized_total_base_units",
            "A must be <= F - R",
        )
    if activated > policy_limit:
        _reject(
            "authorization_exceeds_policy",
            "activated_authorized_total_base_units",
            "A exceeds the policy maximum",
        )
    if settled > activated:
        _reject(
            "settlement_exceeds_authorization",
            "settled_total_base_units",
            "S must be <= A",
        )
    if (sequence == 0) != (activated == 0):
        _reject(
            "activation_state_inconsistent",
            "latest_activated_sequence",
            "sequence and activated total must both be zero or both be non-zero",
        )

    created = _timestamp(channel["created_at"], "created_at")
    updated = _timestamp(channel["updated_at"], "updated_at")
    expires = _timestamp(channel["expires_at"], "expires_at")
    if updated < created:
        _reject("time_order_invalid", "updated_at", "must not precede created_at")
    if expires <= created:
        _reject("time_order_invalid", "expires_at", "must be after created_at")

    status = channel["status"]
    if status not in _CLOSING_STATUSES | _NON_CLOSING_STATUSES:
        _reject("invalid_status", "status", "unsupported channel lifecycle state")
    has_close = "close_requested_at" in channel
    has_deadline = "claim_deadline" in channel
    if has_close != has_deadline:
        _reject(
            "closing_fields_incomplete",
            "close_requested_at",
            "close_requested_at and claim_deadline must appear together",
        )
    if status in _CLOSING_STATUSES | {"closed"} and not has_close:
        _reject("closing_fields_required", "status", "closing requires close timestamps")
    if has_close and status in {"draft", "funding", "active", "settling", "expired"}:
        _reject(
            "closing_fields_forbidden",
            "status",
            "ordinary non-closing states cannot carry close timestamps",
        )
    if has_close:
        close_requested = _timestamp(channel["close_requested_at"], "close_requested_at")
        claim_deadline = _timestamp(channel["claim_deadline"], "claim_deadline")
        grace = channel["policy"]["minimum_close_grace_seconds"]
        if close_requested < created or claim_deadline <= close_requested:
            _reject("close_window_invalid", "claim_deadline", "invalid close window ordering")
        if (claim_deadline - close_requested).total_seconds() < grace:
            _reject("close_grace_too_short", "claim_deadline", "below policy minimum")

    vault = funded - settled - refunded
    if vault < 0:
        _reject("conservation_violation", "funded_total_base_units", "F - S - R is negative")
    return AccountingProjection(
        funded_total_base_units=funded,
        activated_authorized_total_base_units=activated,
        settled_total_base_units=settled,
        refunded_total_base_units=refunded,
        vault_balance_base_units=vault,
        outstanding_right_base_units=activated - settled,
        unallocated_capacity_base_units=funded - refunded - activated,
    )


def validate_funding_transition(
    *,
    previous_funded_total_base_units: str,
    funding: object,
    channel_after: object,
) -> AccountingProjection:
    """Validate one observed funding transition against its resulting snapshot."""

    previous = _amount(previous_funded_total_base_units, "previous_funded_total_base_units")
    event = _closed_object(
        funding,
        field="funding",
        required=_FUNDING_FIELDS,
        allowed=_FUNDING_FIELDS,
    )
    _literal(event["type"], "channel_funding", "funding.type")
    _literal(event["protocol_version"], "1.0.0", "funding.protocol_version")
    _identifier(event["funding_id"], "funding.funding_id")
    _identifier(event["channel_id"], "funding.channel_id")
    _pubkey(event["channel_account"], "funding.channel_account")
    _pubkey(event["mint"], "funding.mint")
    amount = _amount(event["amount_base_units"], "funding.amount_base_units")
    if amount == 0:
        _reject("zero_funding", "funding.amount_base_units", "funding must be positive")
    after_total = _amount(
        event["funded_total_after_base_units"],
        "funding.funded_total_after_base_units",
    )
    if after_total != previous + amount:
        _reject(
            "funding_total_mismatch",
            "funding.funded_total_after_base_units",
            "must equal previous funded total plus amount",
        )
    _integer(event["observed_slot"], field="funding.observed_slot")
    _timestamp(event["observed_at"], "funding.observed_at")
    if (
        not isinstance(event["transaction_signature"], str)
        or _SIGNATURE.fullmatch(event["transaction_signature"]) is None
    ):
        _reject(
            "invalid_transaction_signature",
            "funding.transaction_signature",
            "expected a 64..88 character public signature",
        )

    projection = validate_channel(channel_after)
    channel = channel_after
    assert isinstance(channel, Mapping)  # validated above
    for event_field, channel_field in (
        ("channel_id", "channel_id"),
        ("channel_account", "channel_account"),
        ("mint", "mint"),
    ):
        if event[event_field] != channel[channel_field]:
            _reject(
                "funding_identity_mismatch",
                f"funding.{event_field}",
                f"must equal channel.{channel_field}",
            )
    if after_total != projection.funded_total_base_units:
        _reject(
            "funding_snapshot_mismatch",
            "funding.funded_total_after_base_units",
            "must equal channel funded total",
        )
    if _timestamp(event["observed_at"], "funding.observed_at") > _timestamp(
        channel["updated_at"], "updated_at"
    ):
        _reject(
            "funding_observation_after_snapshot",
            "funding.observed_at",
            "must not be later than channel.updated_at",
        )
    return projection
