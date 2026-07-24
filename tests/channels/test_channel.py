"""FC-PROTO-001 offline Channel and ChannelFunding validation."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


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
        previous_funded_total_base_units="0",
        funding=vector["funding"],
        channel_after=vector["channel_after_funding"],
    )

    assert projection.funded_total_base_units == 100_000_000


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


def test_valid_closing_snapshot_preserves_rights(vector: dict[str, object]) -> None:
    channel = copy.deepcopy(vector["channel_after_funding"])
    channel["status"] = "closing"
    channel["activated_authorized_total_base_units"] = "40000000"
    channel["settled_total_base_units"] = "15000000"
    channel["latest_activated_sequence"] = 3
    channel["latest_activated_voucher_hash"] = vector["vouchers"][2]["voucher_hash"]
    channel["close_requested_at"] = "2026-08-01T01:00:00Z"
    channel["claim_deadline"] = "2026-08-02T01:00:00Z"

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
        ({"observed_at": "2026-08-01T00:02:00Z"}, "funding_observation_after_snapshot"),
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
            previous_funded_total_base_units="0",
            funding=funding,
            channel_after=vector["channel_after_funding"],
        ),
    )


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
