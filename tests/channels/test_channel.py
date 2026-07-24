"""FC-PROTO-001 offline Channel and ChannelFunding validation."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages" / "channel-protocol" / "python"))

from foundry_channel_protocol import (  # noqa: E402
    ChannelValidationError,
    validate_channel,
    validate_funding_transition,
)


@pytest.fixture()
def vector() -> dict[str, object]:
    path = (
        ROOT / "contracts" / "channel" / "test-vectors" / "positive" / "cumulative-channel-v1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def assert_rejected(code: str, operation: object) -> None:
    with pytest.raises(ChannelValidationError) as caught:
        operation()
    assert caught.value.code == code


def funding_snapshot(vector: dict[str, object]) -> dict[str, object]:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "funding"
    channel["funded_total_base_units"] = "0"
    channel["updated_at"] = channel["created_at"]
    return channel


def active_top_up_case(
    vector: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    previous = copy.deepcopy(vector["channel_after_funding"])
    previous["activated_authorized_total_base_units"] = "40000000"
    previous["settled_total_base_units"] = "15000000"
    previous["latest_activated_sequence"] = 3
    previous["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    funding = copy.deepcopy(vector["funding"])
    funding["funding_id"] = "top_up_001"
    funding["amount_base_units"] = "50000000"
    funding["funded_total_after_base_units"] = "150000000"
    funding["observed_at"] = "2026-08-01T00:02:00Z"
    after = copy.deepcopy(previous)
    after["funded_total_base_units"] = "150000000"
    after["updated_at"] = "2026-08-01T00:02:00Z"
    return previous, funding, after


def test_channel_after_funding_derives_conservation(vector: dict[str, object]) -> None:
    projection = validate_channel(vector["channel_after_funding"])

    assert projection.to_dict() == {
        "funded_total_base_units": 100_000_000,
        "activated_authorized_total_base_units": 0,
        "settled_total_base_units": 0,
        "refunded_total_base_units": 0,
        "vault_balance_base_units": 100_000_000,
        "outstanding_right_base_units": 0,
        "unallocated_capacity_base_units": 100_000_000,
    }


def test_reference_40_usdc_settled_projection(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "40000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]

    projection = validate_channel(channel)

    assert projection.vault_balance_base_units == 60_000_000
    assert projection.outstanding_right_base_units == 0
    assert projection.unallocated_capacity_base_units == 60_000_000


def test_partial_settlement_projection(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "15000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]

    projection = validate_channel(channel)

    assert projection.vault_balance_base_units == 85_000_000
    assert projection.outstanding_right_base_units == 25_000_000
    assert projection.unallocated_capacity_base_units == 60_000_000


def test_valid_funding_transition(vector: dict[str, object]) -> None:
    projection = validate_funding_transition(
        previous_channel=funding_snapshot(vector),
        funding=vector["funding"],
        channel_after=vector["channel_after_funding"],
    )

    assert projection.funded_total_base_units == 100_000_000


def test_valid_active_top_up_preserves_accounting(vector: dict[str, object]) -> None:
    previous, funding, after = active_top_up_case(vector)

    projection = validate_funding_transition(
        previous_channel=previous,
        funding=funding,
        channel_after=after,
    )

    assert projection.funded_total_base_units == 150_000_000
    assert projection.activated_authorized_total_base_units == 40_000_000
    assert projection.settled_total_base_units == 15_000_000
    assert projection.refunded_total_base_units == 0


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("funded_total_base_units", 100, "invalid_amount"),
        ("funded_total_base_units", "0100", "invalid_amount"),
        ("funded_total_base_units", "-1", "invalid_amount"),
        ("settled_total_base_units", "1.5", "invalid_amount"),
        ("latest_activated_sequence", True, "invalid_integer"),
        ("latest_activated_voucher_hash", "SHA256:" + "0" * 64, "invalid_hash"),
        ("environment", "mainnet", "invalid_literal"),
        ("network", "solana:mainnet", "invalid_literal"),
    ),
)
def test_malformed_channel_fields_reject(
    vector: dict[str, object], field: str, value: object, code: str
) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel[field] = value

    assert_rejected(code, lambda: validate_channel(channel))


def test_unknown_field_rejects(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["cloud_status"] = "trusted"

    assert_rejected("unknown_field", lambda: validate_channel(channel))


def test_missing_field_rejects(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    del channel["mint"]

    assert_rejected("missing_field", lambda: validate_channel(channel))


@pytest.mark.parametrize(
    ("activated", "settled", "refunded", "policy_limit", "code"),
    (
        ("100000001", "0", "0", "200000000", "authorization_exceeds_capacity"),
        ("40000000", "40000001", "0", "100000000", "settlement_exceeds_authorization"),
        ("0", "0", "100000001", "100000000", "refund_exceeds_funding"),
        ("40000000", "0", "70000000", "100000000", "authorization_exceeds_capacity"),
        ("40000000", "0", "0", "39999999", "authorization_exceeds_policy"),
    ),
)
def test_accounting_violations_reject(
    vector: dict[str, object],
    activated: str,
    settled: str,
    refunded: str,
    policy_limit: str,
    code: str,
) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["activated_authorized_total_base_units"] = activated
    channel["settled_total_base_units"] = settled
    channel["refunded_total_base_units"] = refunded
    channel["policy"]["max_cumulative_authorized_base_units"] = policy_limit
    if activated != "0":
        channel["latest_activated_sequence"] = 1

    assert_rejected(code, lambda: validate_channel(channel))


@pytest.mark.parametrize(
    ("sequence", "activated"),
    ((0, "1"), (1, "0")),
)
def test_activation_sequence_and_total_must_agree(
    vector: dict[str, object], sequence: int, activated: str
) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["latest_activated_sequence"] = sequence
    channel["activated_authorized_total_base_units"] = activated

    assert_rejected("activation_state_inconsistent", lambda: validate_channel(channel))


def test_policy_must_belong_to_channel(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["policy"]["channel_id"] = "other_channel"

    assert_rejected("policy_channel_mismatch", lambda: validate_channel(channel))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("funded_total_base_units", "1"),
        ("activated_authorized_total_base_units", "1"),
        ("settled_total_base_units", "1"),
        ("refunded_total_base_units", "1"),
    ),
)
def test_draft_requires_zero_accounting(vector: dict[str, object], field: str, value: str) -> None:
    channel = funding_snapshot(vector)
    channel["status"] = "draft"
    channel[field] = value
    if field in {"activated_authorized_total_base_units", "settled_total_base_units"}:
        channel["funded_total_base_units"] = "1"
        channel["activated_authorized_total_base_units"] = "1"
        channel["latest_activated_sequence"] = 1
    elif field == "refunded_total_base_units":
        channel["funded_total_base_units"] = "1"

    assert_rejected("draft_accounting_nonzero", lambda: validate_channel(channel))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("activated_authorized_total_base_units", "1"),
        ("settled_total_base_units", "1"),
        ("refunded_total_base_units", "1"),
    ),
)
def test_funding_state_rejects_allocated_accounting(
    vector: dict[str, object], field: str, value: str
) -> None:
    channel = funding_snapshot(vector)
    channel["funded_total_base_units"] = "1"
    channel[field] = value
    if field in {"activated_authorized_total_base_units", "settled_total_base_units"}:
        channel["activated_authorized_total_base_units"] = "1"
        channel["latest_activated_sequence"] = 1

    assert_rejected("funding_accounting_invalid", lambda: validate_channel(channel))


def test_active_requires_positive_funding(vector: dict[str, object]) -> None:
    channel = funding_snapshot(vector)
    channel["status"] = "active"

    assert_rejected("funding_required", lambda: validate_channel(channel))


def test_closing_requires_both_timestamps(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closing"
    channel["close_requested_at"] = "2026-08-01T01:00:00Z"

    assert_rejected("closing_fields_incomplete", lambda: validate_channel(channel))


def test_closing_enforces_minimum_claim_window(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closing"
    channel["close_requested_at"] = "2026-08-01T01:00:00Z"
    channel["claim_deadline"] = "2026-08-01T02:00:00Z"
    channel["updated_at"] = "2026-08-01T01:00:00Z"

    assert_rejected("close_grace_too_short", lambda: validate_channel(channel))


def test_active_channel_cannot_carry_close_timestamps(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["close_requested_at"] = "2026-08-01T01:00:00Z"
    channel["claim_deadline"] = "2026-08-02T01:00:00Z"

    assert_rejected("closing_fields_forbidden", lambda: validate_channel(channel))


def test_closed_channel_requires_close_timestamps(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closed"

    assert_rejected("closing_fields_required", lambda: validate_channel(channel))


def test_closing_request_cannot_follow_snapshot_update(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closing"
    channel["close_requested_at"] = "2026-08-01T00:02:00Z"
    channel["claim_deadline"] = "2026-08-02T00:02:00Z"

    assert_rejected("close_snapshot_order_invalid", lambda: validate_channel(channel))


def test_closed_rejects_outstanding_right(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closed"
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "15000000"
    channel["refunded_total_base_units"] = "60000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    channel["close_requested_at"] = "2026-08-01T00:01:00Z"
    channel["claim_deadline"] = "2026-08-02T00:01:00Z"
    channel["updated_at"] = "2026-08-02T00:01:00Z"

    assert_rejected("closed_outstanding_right", lambda: validate_channel(channel))


def test_closed_rejects_nonzero_vault(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closed"
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "40000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    channel["close_requested_at"] = "2026-08-01T00:01:00Z"
    channel["claim_deadline"] = "2026-08-02T00:01:00Z"
    channel["updated_at"] = "2026-08-02T00:01:00Z"

    assert_rejected("closed_vault_nonzero", lambda: validate_channel(channel))


def test_closed_finalization_cannot_precede_deadline(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closed"
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "40000000"
    channel["refunded_total_base_units"] = "60000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    channel["close_requested_at"] = "2026-08-01T00:01:00Z"
    channel["claim_deadline"] = "2026-08-02T00:01:00Z"

    assert_rejected("closed_before_claim_deadline", lambda: validate_channel(channel))


def test_valid_closed_snapshot_has_zero_vault_and_no_outstanding_right(
    vector: dict[str, object],
) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closed"
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "40000000"
    channel["refunded_total_base_units"] = "60000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    channel["close_requested_at"] = "2026-08-01T00:01:00Z"
    channel["claim_deadline"] = "2026-08-02T00:01:00Z"
    channel["updated_at"] = "2026-08-02T00:01:00Z"

    projection = validate_channel(channel)

    assert projection.vault_balance_base_units == 0
    assert projection.outstanding_right_base_units == 0


def test_valid_closing_snapshot_preserves_rights(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closing"
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "15000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    channel["close_requested_at"] = "2026-08-01T01:00:00Z"
    channel["claim_deadline"] = "2026-08-02T01:00:00Z"
    channel["updated_at"] = "2026-08-01T01:00:00Z"

    projection = validate_channel(channel)

    assert projection.outstanding_right_base_units == 25_000_000
    assert projection.unallocated_capacity_base_units == 60_000_000


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        ({"amount_base_units": "0"}, "zero_funding"),
        ({"funded_total_after_base_units": "99999999"}, "funding_total_mismatch"),
        ({"channel_id": "other_channel"}, "funding_identity_mismatch"),
        ({"mint": "11111111111111111111111111111111"}, "funding_identity_mismatch"),
        ({"observed_at": "2026-08-01T00:02:00Z"}, "funding_time_order_invalid"),
        ({"transaction_signature": "not-base58!"}, "invalid_transaction_signature"),
    ),
)
def test_inconsistent_funding_rejects(
    vector: dict[str, object], mutation: dict[str, object], code: str
) -> None:
    funding = copy.deepcopy(vector["funding"])
    funding.update(mutation)

    assert_rejected(
        code,
        lambda: validate_funding_transition(
            previous_channel=funding_snapshot(vector),
            funding=funding,
            channel_after=vector["channel_after_funding"],
        ),
    )


@pytest.mark.parametrize("status", ("draft", "closing", "closed", "expired"))
def test_funding_rejects_forbidden_previous_lifecycle(
    vector: dict[str, object], status: str
) -> None:
    previous = copy.deepcopy(vector["channel_after_funding"])
    if status == "draft":
        previous = funding_snapshot(vector)
        previous["status"] = "draft"
    elif status == "closing":
        previous["status"] = "closing"
        previous["close_requested_at"] = "2026-08-01T00:01:00Z"
        previous["claim_deadline"] = "2026-08-02T00:01:00Z"
    elif status == "closed":
        previous["status"] = "closed"
        previous["activated_authorized_total_base_units"] = "40000000"
        previous["settled_total_base_units"] = "40000000"
        previous["refunded_total_base_units"] = "60000000"
        previous["latest_activated_sequence"] = 3
        previous["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
        previous["close_requested_at"] = "2026-08-01T00:01:00Z"
        previous["claim_deadline"] = "2026-08-02T00:01:00Z"
        previous["updated_at"] = "2026-08-02T00:01:00Z"
    else:
        previous["status"] = "expired"

    assert_rejected(
        "funding_lifecycle_forbidden",
        lambda: validate_funding_transition(
            previous_channel=previous,
            funding=vector["funding"],
            channel_after=vector["channel_after_funding"],
        ),
    )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("environment", "other", "invalid_literal"),
        ("network", "solana:other", "invalid_literal"),
        ("genesis_hash", "11111111111111111111111111111111", "funding_immutable_field_changed"),
        ("program_id", "11111111111111111111111111111111", "funding_immutable_field_changed"),
        ("channel_id", "other_channel", "policy_channel_mismatch"),
        ("channel_account", "11111111111111111111111111111111", "funding_identity_mismatch"),
        ("epoch", 1, "funding_immutable_field_changed"),
        ("sender", "11111111111111111111111111111111", "funding_immutable_field_changed"),
        (
            "recipient_claim_pubkey",
            "11111111111111111111111111111111",
            "funding_immutable_field_changed",
        ),
        (
            "recipient_wallet",
            "11111111111111111111111111111111",
            "funding_immutable_field_changed",
        ),
        ("mint", "11111111111111111111111111111111", "funding_identity_mismatch"),
        ("decimals", 9, "funding_immutable_field_changed"),
        (
            "vault_token_account",
            "9zsJvRFTxAG5sBuXhjMDZkgWb9oqQbK8gDywo7mUMNKb",
            "funding_immutable_field_changed",
        ),
        (
            "activated_authorized_total_base_units",
            "41000000",
            "funding_immutable_field_changed",
        ),
        ("settled_total_base_units", "16000000", "funding_immutable_field_changed"),
        ("refunded_total_base_units", "1", "funding_immutable_field_changed"),
        ("latest_activated_sequence", 4, "funding_immutable_field_changed"),
        (
            "latest_activated_voucher_hash",
            "sha256:" + "1" * 64,
            "funding_immutable_field_changed",
        ),
        ("expires_at", "2026-08-04T00:00:00Z", "funding_immutable_field_changed"),
        ("created_at", "2026-07-31T00:00:00Z", "funding_immutable_field_changed"),
    ),
)
def test_top_up_rejects_immutable_field_mutation(
    vector: dict[str, object], field: str, value: object, code: str
) -> None:
    previous, funding, after = active_top_up_case(vector)
    previous["recipient_wallet"] = vector["constants"]["recipient_wallet"]
    after["recipient_wallet"] = vector["constants"]["recipient_wallet"]
    after[field] = value

    assert_rejected(
        code,
        lambda: validate_funding_transition(
            previous_channel=previous,
            funding=funding,
            channel_after=after,
        ),
    )


def test_top_up_rejects_policy_mutation(vector: dict[str, object]) -> None:
    previous, funding, after = active_top_up_case(vector)
    after["policy"]["max_cumulative_authorized_base_units"] = "150000000"

    assert_rejected(
        "funding_immutable_field_changed",
        lambda: validate_funding_transition(
            previous_channel=previous,
            funding=funding,
            channel_after=after,
        ),
    )


def test_top_up_requires_prior_policy_permission(vector: dict[str, object]) -> None:
    previous, funding, after = active_top_up_case(vector)
    previous["policy"]["allow_top_up"] = False
    after["policy"]["allow_top_up"] = False

    assert_rejected(
        "top_up_forbidden",
        lambda: validate_funding_transition(
            previous_channel=previous,
            funding=funding,
            channel_after=after,
        ),
    )


def test_funding_transition_rejects_invalid_after_status(vector: dict[str, object]) -> None:
    previous = funding_snapshot(vector)
    after = copy.deepcopy(vector["channel_after_funding"])
    after["status"] = "settling"

    assert_rejected(
        "funding_status_transition_invalid",
        lambda: validate_funding_transition(
            previous_channel=previous,
            funding=vector["funding"],
            channel_after=after,
        ),
    )


def test_funding_observation_must_follow_previous_snapshot(vector: dict[str, object]) -> None:
    previous, funding, after = active_top_up_case(vector)
    previous["updated_at"] = "2026-08-01T00:03:00Z"
    after["updated_at"] = "2026-08-01T00:03:00Z"

    assert_rejected(
        "funding_time_order_invalid",
        lambda: validate_funding_transition(
            previous_channel=previous,
            funding=funding,
            channel_after=after,
        ),
    )


def test_u64_maximum_is_accepted_by_reference_and_schema(vector: dict[str, object]) -> None:
    channel = funding_snapshot(vector)
    channel["funded_total_base_units"] = str(2**64 - 1)
    schema = json.loads(
        (ROOT / "contracts" / "channel" / "channel.schema.json").read_text(encoding="utf-8")
    )

    projection = validate_channel(channel)
    errors = list(Draft202012Validator(schema).iter_errors(channel))

    assert projection.funded_total_base_units == 2**64 - 1
    assert errors == []


def test_u64_overflow_is_rejected_by_reference_and_schema(vector: dict[str, object]) -> None:
    channel = funding_snapshot(vector)
    channel["funded_total_base_units"] = str(2**64)
    schema = json.loads(
        (ROOT / "contracts" / "channel" / "channel.schema.json").read_text(encoding="utf-8")
    )

    assert_rejected("amount_out_of_range", lambda: validate_channel(channel))
    assert list(Draft202012Validator(schema).iter_errors(channel))


def test_validator_has_no_network_import() -> None:
    source = (
        ROOT
        / "packages"
        / "channel-protocol"
        / "python"
        / "foundry_channel_protocol"
        / "channel.py"
    ).read_text(encoding="utf-8")

    assert "socket" not in source
    assert "requests" not in source
    assert "urllib" not in source
    assert "solana.rpc" not in source
