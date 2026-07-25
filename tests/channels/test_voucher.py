"""FC-PROTO-002 cumulative voucher and durable reference-ledger tests."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import rfc8785
from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages" / "channel-protocol" / "python"))

from foundry_channel_protocol import (  # noqa: E402
    ReferenceVoucherLedger,
    VoucherContext,
    VoucherValidationError,
    canonical_voucher_payload,
    verify_voucher,
    voucher_payload_hash,
)


NOW = datetime(2026, 8, 1, 0, 6, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 1, 0, 7, tzinfo=timezone.utc)


@pytest.fixture()
def vector() -> dict[str, Any]:
    return json.loads(
        (
            ROOT
            / "contracts"
            / "channel"
            / "test-vectors"
            / "positive"
            / "cumulative-channel-v1.json"
        ).read_text(encoding="utf-8")
    )


@pytest.fixture()
def voucher(vector: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(vector["vouchers"][2])


@pytest.fixture()
def context(vector: dict[str, Any]) -> VoucherContext:
    constants = vector["constants"]
    previous = vector["vouchers"][1]
    return VoucherContext(
        environment=constants["environment"],
        network=constants["network"],
        genesis_hash=constants["genesis_hash"],
        program_id=constants["program_id"],
        channel_id=constants["channel_id"],
        channel_account=constants["channel_account"],
        epoch=0,
        sender=constants["sender"],
        recipient_claim_pubkey=constants["claim_pubkey"],
        mint=constants["mint"],
        funded_total_base_units=100_000_000,
        refunded_total_base_units=0,
        policy_limit_base_units=100_000_000,
        channel_expires_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        latest_activated_sequence=2,
        latest_activated_total_base_units=25_000_000,
        latest_activated_voucher_hash=previous["voucher_hash"],
    )


class RecordingVerifier:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.calls: list[tuple[str, bytes, str]] = []

    def __call__(self, public_key: str, message: bytes, signature: str) -> bool:
        self.calls.append((public_key, message, signature))
        return self.result


def rehash(voucher: dict[str, Any]) -> dict[str, Any]:
    voucher["voucher_hash"] = voucher_payload_hash(voucher["payload"])
    return voucher


def rehash_untrusted(voucher: dict[str, Any]) -> dict[str, Any]:
    voucher["voucher_hash"] = (
        "sha256:" + hashlib.sha256(rfc8785.dumps(voucher["payload"])).hexdigest()
    )
    return voucher


def next_voucher(
    voucher: dict[str, Any], *, sequence: int, total: int, issued_second: int
) -> dict[str, Any]:
    updated = copy.deepcopy(voucher)
    updated["payload"]["sequence"] = sequence
    updated["payload"]["cumulative_authorized_base_units"] = str(total)
    updated["payload"]["issued_at"] = f"2026-08-01T00:0{issued_second}:00Z"
    return rehash(updated)


def assert_rejected(code: str, operation: Any) -> None:
    with pytest.raises(VoucherValidationError) as caught:
        operation()
    assert caught.value.code == code


def test_positive_vector_has_normative_canonical_hash(
    voucher: dict[str, Any],
) -> None:
    canonical = canonical_voucher_payload(voucher["payload"])

    assert canonical.startswith(b'{"channel_account":')
    assert voucher_payload_hash(voucher["payload"]) == voucher["voucher_hash"]
    assert (
        voucher["voucher_hash"]
        == "sha256:8a3283d61a75e1bbe987941601e8f28708875913fd0dfef0fa399c6a7dd296e2"
    )


def test_schema_and_runtime_share_u64_domain(voucher: dict[str, Any]) -> None:
    schema = json.loads(
        (ROOT / "contracts" / "channel" / "channel-voucher.schema.json").read_text(encoding="utf-8")
    )
    maximum = copy.deepcopy(voucher)
    maximum["payload"]["cumulative_authorized_base_units"] = str(2**64 - 1)
    rehash(maximum)
    overflow = copy.deepcopy(maximum)
    overflow["payload"]["cumulative_authorized_base_units"] = str(2**64)

    assert list(Draft202012Validator(schema).iter_errors(maximum)) == []
    assert list(Draft202012Validator(schema).iter_errors(overflow))
    assert_rejected(
        "amount_out_of_range",
        lambda: canonical_voucher_payload(overflow["payload"]),
    )

    unsafe_sequence = copy.deepcopy(voucher)
    unsafe_sequence["payload"]["sequence"] = 2**53
    assert list(Draft202012Validator(schema).iter_errors(unsafe_sequence))
    assert_rejected(
        "invalid_integer",
        lambda: canonical_voucher_payload(unsafe_sequence["payload"]),
    )


def test_verifier_binds_signature_to_exact_canonical_payload(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    signature = RecordingVerifier()

    verified = verify_voucher(
        voucher,
        context=context,
        now=NOW,
        signature_verifier=signature,
    )

    assert verified.sequence == 3
    assert verified.cumulative_authorized_base_units == 40_000_000
    assert signature.calls == [
        (
            context.sender,
            canonical_voucher_payload(voucher["payload"]),
            voucher["sender_signature"],
        )
    ]


def test_mutated_payload_with_stale_hash_rejects(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    voucher["payload"]["cumulative_authorized_base_units"] = "41000000"

    assert_rejected(
        "voucher_hash_mismatch",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_invalid_signature_rejects(voucher: dict[str, Any], context: VoucherContext) -> None:
    assert_rejected(
        "invalid_sender_signature",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(False),
        ),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("environment", "mainnet"),
        ("network", "solana:mainnet"),
        ("genesis_hash", "11111111111111111111111111111111"),
        ("program_id", "11111111111111111111111111111111"),
        ("channel_id", "other_channel"),
        ("channel_account", "11111111111111111111111111111111"),
        ("epoch", 1),
        ("sender", "11111111111111111111111111111111"),
        ("recipient_claim_pubkey", "11111111111111111111111111111111"),
        ("mint", "11111111111111111111111111111111"),
    ),
)
def test_replay_across_every_context_dimension_rejects(
    voucher: dict[str, Any],
    context: VoucherContext,
    field: str,
    value: Any,
) -> None:
    voucher["payload"][field] = value
    rehash_untrusted(voucher)

    with pytest.raises(VoucherValidationError):
        verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        )


def test_signed_object_domain_is_explicit_and_not_reusable(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    voucher["payload"]["domain"] = "foundry.channels.recipient-binding"
    rehash_untrusted(voucher)

    assert_rejected(
        "domain_mismatch",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


@pytest.mark.parametrize("case_number", range(1, 8))
def test_shared_negative_voucher_vectors_have_stable_errors(
    voucher: dict[str, Any],
    context: VoucherContext,
    case_number: int,
) -> None:
    vector_path = next(
        (ROOT / "contracts" / "channel" / "test-vectors" / "negative").glob(
            f"{case_number:02d}-*.json"
        )
    )
    negative = json.loads(vector_path.read_text(encoding="utf-8"))
    assert negative["target"] == "voucher:3"
    path = negative["mutation"]["path"].split(".")
    assert path[0] == "payload" and len(path) == 2
    voucher["payload"][path[1]] = negative["mutation"]["value"]
    rehash_untrusted(voucher)

    assert_rejected(
        negative["expected_error"],
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_wrong_previous_activated_hash_rejects(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    voucher["payload"]["previous_activated_voucher_hash"] = "sha256:" + ("1" * 64)
    rehash(voucher)

    assert_rejected(
        "previous_voucher_hash_mismatch",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_stale_sequence_and_decreasing_total_reject(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    voucher["payload"]["sequence"] = 2
    rehash(voucher)
    assert_rejected(
        "sequence_not_monotonic",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )

    voucher["payload"]["sequence"] = 3
    voucher["payload"]["cumulative_authorized_base_units"] = "24000000"
    rehash(voucher)
    assert_rejected(
        "cumulative_amount_decreased",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_equal_cumulative_total_is_non_decreasing(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    voucher["payload"]["cumulative_authorized_base_units"] = "25000000"
    rehash(voucher)

    verified = verify_voucher(
        voucher,
        context=context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )

    assert verified.cumulative_authorized_base_units == 25_000_000


def test_context_activated_hash_must_match_zero_or_nonzero_state(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    invalid_contexts = (
        replace(
            context,
            latest_activated_sequence=0,
            latest_activated_total_base_units=0,
        ),
        replace(
            context,
            latest_activated_voucher_hash="sha256:" + ("0" * 64),
        ),
    )

    for invalid_context in invalid_contexts:
        assert_rejected(
            "invalid_context_accounting",
            lambda invalid_context=invalid_context: verify_voucher(
                voucher,
                context=invalid_context,
                now=NOW,
                signature_verifier=RecordingVerifier(),
            ),
        )


def test_first_sequenced_voucher_cannot_authorize_zero(
    voucher: dict[str, Any], context: VoucherContext
) -> None:
    empty_context = replace(
        context,
        latest_activated_sequence=0,
        latest_activated_total_base_units=0,
        latest_activated_voucher_hash="sha256:" + ("0" * 64),
    )
    voucher["payload"]["sequence"] = 1
    voucher["payload"]["previous_activated_voucher_hash"] = "sha256:" + ("0" * 64)
    voucher["payload"]["cumulative_authorized_base_units"] = "0"
    rehash(voucher)

    assert_rejected(
        "zero_cumulative_authorization",
        lambda: verify_voucher(
            voucher,
            context=empty_context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_funding_policy_and_expiry_guards(voucher: dict[str, Any], context: VoucherContext) -> None:
    overfunded = copy.deepcopy(voucher)
    overfunded["payload"]["cumulative_authorized_base_units"] = "100000001"
    rehash(overfunded)
    assert_rejected(
        "authorization_exceeds_funding",
        lambda: verify_voucher(
            overfunded,
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )

    restricted = replace(context, policy_limit_base_units=39_000_000)
    assert_rejected(
        "authorization_exceeds_policy",
        lambda: verify_voucher(
            voucher,
            context=restricted,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )

    assert_rejected(
        "voucher_expired",
        lambda: verify_voucher(
            voucher,
            context=context,
            now=datetime(2026, 8, 2, tzinfo=timezone.utc),
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_ledger_persists_only_non_authoritative_states(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    path = tmp_path / "voucher.sqlite3"
    ledger = ReferenceVoucherLedger(path)

    issued = ledger.record_issued("submission_003", voucher, observed_at=NOW)
    verified = ledger.verify_issued(
        "submission_003",
        context=context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )
    requested = ledger.request_activation(
        "submission_003",
        context=context,
        observed_at=LATER,
    )

    assert issued.state == "issued"
    assert verified.state == "verified"
    assert requested.state == "activation_requested"
    assert [event["state"] for event in ledger.events("submission_003")] == [
        "issued",
        "verified",
        "activation_requested",
    ]
    assert not hasattr(ledger, "activate")
    assert "activated" not in {event["state"] for event in ledger.events("submission_003")}

    restarted = ReferenceVoucherLedger(path)
    assert restarted.get("submission_003") == requested


def test_rejection_is_durable_and_has_no_monotonic_effect(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    voucher["payload"]["sequence"] = 2
    rehash(voucher)
    ledger.record_issued("stale_002", voucher, observed_at=NOW)

    assert_rejected(
        "sequence_not_monotonic",
        lambda: ledger.verify_issued(
            "stale_002",
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )

    assert ledger.get("stale_002").state == "rejected"
    assert ledger.get("stale_002").error_code == "sequence_not_monotonic"
    assert ledger.events("stale_002")[-1]["state"] == "rejected"


def test_signature_verifier_failure_is_retryable_not_terminal(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("transient_signature", voucher, observed_at=NOW)

    def unavailable(_public_key: str, _message: bytes, _signature: str) -> bool:
        raise RuntimeError("provider unavailable")

    assert_rejected(
        "signature_verifier_failed",
        lambda: ledger.verify_issued(
            "transient_signature",
            context=context,
            now=NOW,
            signature_verifier=unavailable,
        ),
    )
    assert ledger.get("transient_signature").state == "issued"
    assert ledger.get("transient_signature").error_code == "signature_verifier_failed"

    retried = ledger.verify_issued(
        "transient_signature",
        context=context,
        now=LATER,
        signature_verifier=RecordingVerifier(),
    )

    assert retried.state == "verified"
    assert retried.error_code is None


def test_activation_request_revalidates_expiry_and_current_context(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("expiring", voucher, observed_at=NOW)
    ledger.verify_issued(
        "expiring",
        context=context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )

    assert_rejected(
        "voucher_expired",
        lambda: ledger.request_activation(
            "expiring",
            context=context,
            observed_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        ),
    )
    assert ledger.get("expiring").state == "rejected"
    assert ledger.get("expiring").error_code == "voucher_expired"


def test_activation_request_rejects_changed_authoritative_context(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("changed_context", voucher, observed_at=NOW)
    ledger.verify_issued(
        "changed_context",
        context=context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )
    changed = replace(context, program_id="11111111111111111111111111111111")

    assert_rejected(
        "activation_context_changed",
        lambda: ledger.request_activation(
            "changed_context",
            context=changed,
            observed_at=LATER,
        ),
    )
    assert ledger.get("changed_context").state == "rejected"


def test_journal_time_never_regresses(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("time_guard", voucher, observed_at=LATER)

    assert_rejected(
        "journal_time_regressed",
        lambda: ledger.verify_issued(
            "time_guard",
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )
    assert ledger.get("time_guard").state == "issued"

    ledger.verify_issued(
        "time_guard",
        context=context,
        now=LATER,
        signature_verifier=RecordingVerifier(),
    )
    assert_rejected(
        "journal_time_regressed",
        lambda: ledger.request_activation(
            "time_guard",
            context=context,
            observed_at=NOW,
        ),
    )
    assert ledger.get("time_guard").state == "verified"


def test_ledger_enforces_monotonic_issued_sequence_and_total(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("submission_003", voucher, observed_at=NOW)
    ledger.verify_issued(
        "submission_003",
        context=context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )
    lower = next_voucher(voucher, sequence=4, total=39_000_000, issued_second=5)
    ledger.record_issued("submission_004", lower, observed_at=NOW)

    assert_rejected(
        "cumulative_amount_decreased",
        lambda: ledger.verify_issued(
            "submission_004",
            context=context,
            now=NOW,
            signature_verifier=RecordingVerifier(),
        ),
    )


def test_ledger_monotonicity_is_partitioned_by_full_domain(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("original_domain", voucher, observed_at=NOW)
    ledger.verify_issued(
        "original_domain",
        context=context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )

    alternate_program = "11111111111111111111111111111111"
    alternate_context = replace(
        context,
        program_id=alternate_program,
        latest_activated_sequence=0,
        latest_activated_total_base_units=0,
        latest_activated_voucher_hash="sha256:" + ("0" * 64),
    )
    alternate = copy.deepcopy(voucher)
    alternate["payload"]["program_id"] = alternate_program
    alternate["payload"]["sequence"] = 1
    alternate["payload"]["previous_activated_voucher_hash"] = "sha256:" + ("0" * 64)
    alternate["payload"]["cumulative_authorized_base_units"] = "10000000"
    rehash(alternate)
    ledger.record_issued("alternate_domain", alternate, observed_at=NOW)

    record = ledger.verify_issued(
        "alternate_domain",
        context=alternate_context,
        now=NOW,
        signature_verifier=RecordingVerifier(),
    )

    assert record.state == "verified"
    assert record.sequence == 1


def test_submission_id_is_idempotent_but_cannot_rebind_bytes(
    tmp_path: Path, voucher: dict[str, Any]
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    first = ledger.record_issued("submission_003", voucher, observed_at=NOW)
    again = ledger.record_issued("submission_003", voucher, observed_at=LATER)
    mutated = copy.deepcopy(voucher)
    mutated["payload"]["sequence"] = 4

    assert first == again
    assert_rejected(
        "submission_id_collision",
        lambda: ledger.record_issued("submission_003", mutated, observed_at=LATER),
    )


def test_concurrent_verification_never_regresses_latest_issued_state(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    path = tmp_path / "voucher.sqlite3"
    ledger = ReferenceVoucherLedger(path)
    fourth = next_voucher(voucher, sequence=4, total=50_000_000, issued_second=5)
    fifth = next_voucher(voucher, sequence=5, total=60_000_000, issued_second=5)
    ledger.record_issued("submission_004", fourth, observed_at=NOW)
    ledger.record_issued("submission_005", fifth, observed_at=NOW)

    def verify(submission_id: str) -> str:
        try:
            return ledger.verify_issued(
                submission_id,
                context=context,
                now=NOW,
                signature_verifier=RecordingVerifier(),
            ).state
        except VoucherValidationError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(verify, ("submission_004", "submission_005")))

    assert ledger.get("submission_005").state == "verified"
    assert ledger.get("submission_005").sequence == 5
    assert results[1] == "verified"
    assert results[0] in {"verified", "sequence_not_monotonic"}


def test_activation_request_requires_verified_state(
    tmp_path: Path, voucher: dict[str, Any], context: VoucherContext
) -> None:
    ledger = ReferenceVoucherLedger(tmp_path / "voucher.sqlite3")
    ledger.record_issued("submission_003", voucher, observed_at=NOW)

    assert_rejected(
        "activation_request_forbidden",
        lambda: ledger.request_activation(
            "submission_003",
            context=context,
            observed_at=NOW,
        ),
    )


def test_sqlite_connections_close_deterministically(
    tmp_path: Path, voucher: dict[str, Any]
) -> None:
    path = tmp_path / "voucher.sqlite3"
    ledger = ReferenceVoucherLedger(path)
    ledger.record_issued("close_handles", voucher, observed_at=NOW)
    ledger.get("close_handles")
    ledger.events("close_handles")

    path.unlink()

    assert not path.exists()
