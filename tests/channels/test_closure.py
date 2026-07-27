"""FC-PROTO-005 offline close, refund, and epoch tests."""

from __future__ import annotations

import copy
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages" / "channel-protocol" / "python"))
sys.path.insert(0, str(ROOT / "packages" / "external-execution-protocol" / "python"))

from foundry_channel_protocol import (  # noqa: E402
    ClosureError,
    ClosureRuntime,
    activation_is_eligible,
    epoch_transition_eligibility,
    freeze_closure,
    make_refund_request,
    project_refund,
    request_close,
    validate_finalization,
)
from foundry_external_execution_protocol import canonicalize, sha256_digest  # noqa: E402


NOW = datetime(2026, 8, 1, 0, 5, tzinfo=UTC)
DEADLINE = NOW + timedelta(seconds=60)
GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
PROGRAM = "BPFLoaderUpgradeab1e11111111111111111111111"
CHANNEL_ACCOUNT = "EUt7wV4f5bzSFJccZ5aafJV7zykZfyWz9rctaug7hVxd"
SENDER = "9zsJvRFTxAG5sBuXhjMDZkgWb9oqQbK8gDywo7mUMNKb"
CLAIM_KEY = "9LAfXjiLxADaSQw2ipGQq5kPyzCy8F2hZhnP4YLBEReV"
MINT = "2tUzxADKHWxwTpihHuuzwfoGhYBY7735s2QXEuUcNX3k"
VAULT = "11111111111111111111111111111111"
SIGNATURE = "refund-signature-fixture"


class FixtureObservationVerifier:
    source_id = "independent_fixture"

    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted

    def verify(self, observation: dict) -> bool:
        return self.accepted and observation["source_id"] == self.source_id


def canonical_hash(value: dict) -> str:
    return sha256_digest(canonicalize(value))


def rehash(value: dict, field: str) -> dict:
    result = copy.deepcopy(value)
    result.pop(field, None)
    result[field] = canonical_hash(result)
    return result


def channel(
    *,
    status: str = "active",
    activated: int = 10_000_000,
    settled: int = 0,
    refunded: int = 0,
    latest_sequence: int = 1,
    epoch: int = 0,
    updated_at: str = "2026-08-01T00:04:00Z",
) -> dict:
    result = {
        "type": "channel",
        "protocol_version": "1.0.0",
        "account_version": 1,
        "environment": "devnet",
        "network": "solana:devnet",
        "genesis_hash": GENESIS,
        "program_id": PROGRAM,
        "channel_id": "channel_closure_001",
        "channel_account": CHANNEL_ACCOUNT,
        "epoch": epoch,
        "sender": SENDER,
        "recipient_claim_pubkey": CLAIM_KEY,
        "mint": MINT,
        "decimals": 6,
        "vault_token_account": VAULT,
        "funded_total_base_units": "100000000",
        "activated_authorized_total_base_units": str(activated),
        "settled_total_base_units": str(settled),
        "refunded_total_base_units": str(refunded),
        "latest_activated_sequence": latest_sequence,
        "latest_activated_voucher_hash": (
            "sha256:" + ("0" * 64)
            if latest_sequence == 0
            else "sha256:" + (f"{latest_sequence:x}"[-1] * 64)
        ),
        "status": status,
        "expires_at": "2026-08-03T00:00:00Z",
        "policy": {
            "type": "channel_policy",
            "protocol_version": "1.0.0",
            "channel_id": "channel_closure_001",
            "max_cumulative_authorized_base_units": "100000000",
            "allow_partial_settlement": True,
            "allow_top_up": True,
            "minimum_close_grace_seconds": 60,
            "rebind_mode": "disabled",
        },
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": updated_at,
    }
    if status in {"closing", "closed"}:
        result["close_requested_at"] = "2026-08-01T00:05:00Z"
        result["claim_deadline"] = "2026-08-01T00:06:00Z"
    return result


def closure_flow(
    *,
    activated_at_freeze: int = 40_000_000,
    settled_at_freeze: int = 15_000_000,
    refunded_at_freeze: int = 0,
    operation_states: tuple[str, ...] = (),
) -> tuple[dict, dict, dict, dict]:
    initial = channel()
    artifacts = request_close(
        initial,
        closure_id="closure_001",
        idempotency_key="close_key_001",
        now=NOW,
        claim_deadline=DEADLINE,
    )
    closing = channel(
        status="closing",
        activated=activated_at_freeze,
        settled=settled_at_freeze,
        refunded=refunded_at_freeze,
        latest_sequence=3,
        updated_at="2026-08-01T00:06:00Z",
    )
    frozen = freeze_closure(
        artifacts.request,
        artifacts.snapshot_at_request,
        closing,
        now=DEADLINE,
        operation_states=operation_states,
    )
    return initial, artifacts.request, artifacts.snapshot_at_request, frozen


def refund_request(
    closure_request: dict,
    frozen: dict,
    *,
    amount: int = 60_000_000,
    reason: str = "post_claim_window_unallocated",
    suffix: str = "001",
    expires_in: timedelta = timedelta(minutes=5),
) -> dict:
    return make_refund_request(
        closure_request,
        frozen,
        refund_id=f"refund_{suffix}",
        idempotency_key=f"refund_key_{suffix}",
        reason=reason,
        requested_base_units=amount,
        now=DEADLINE,
        expires_at=DEADLINE + expires_in,
    )


def technical_receipt(request: dict, *, outcome: str = "accepted") -> dict:
    unsigned = {
        "type": "technical_refund_receipt",
        "protocol_version": "1.0.0",
        "refund_id": request["refund_id"],
        "refund_request_hash": request["request_hash"],
        "execution_request_id": f"execution_{request['refund_id']}",
        "execution_commitment_hash": "sha256:" + ("c" * 64),
        "outcome": outcome,
        "signature_status": "known" if outcome == "accepted" else "unknown",
        "technical_status": "fixture",
        "observed_at": "2026-08-01T00:06:05Z",
    }
    if outcome == "accepted":
        unsigned["transaction_signature"] = SIGNATURE
    return {**unsigned, "receipt_hash": canonical_hash(unsigned)}


def refund_observation(request: dict, projection: dict, **changes: object) -> dict:
    unsigned = {
        "type": "channel_refund_observation",
        "protocol_version": "1.0.0",
        "source_id": "independent_fixture",
        "channel_id": request["channel"]["channel_id"],
        "channel_account": request["channel"]["channel_account"],
        "epoch": request["channel"]["epoch"],
        "mint": request["channel"]["mint"],
        "destination": request["destination"],
        "refund_id": request["refund_id"],
        "transaction_signature": SIGNATURE,
        "funded_total_base_units": projection["funded_total_base_units"],
        "activated_total_base_units": projection["activated_total_base_units"],
        "settled_total_base_units": projection["settled_total_base_units"],
        "refunded_total_before_base_units": projection["refunded_total_before_base_units"],
        "refunded_total_after_base_units": projection["refunded_total_after_base_units"],
        "vault_balance_before_base_units": projection["vault_balance_before_base_units"],
        "vault_balance_after_base_units": projection["vault_balance_after_base_units"],
        "observed_at": "2026-08-01T00:06:10Z",
    }
    unsigned.update(changes)
    return {**unsigned, "observation_hash": canonical_hash(unsigned)}


def assert_error(code: str, callback) -> None:
    with pytest.raises(ClosureError) as captured:
        callback()
    assert captured.value.code == code


def test_request_and_freeze_use_distinct_deterministic_snapshots() -> None:
    _, request, at_request, frozen = closure_flow()

    assert request["request_hash"] == canonical_hash(
        {key: value for key, value in request.items() if key != "request_hash"}
    )
    assert at_request["activated_total_base_units"] == "10000000"
    assert frozen["activated_total_base_units"] == "40000000"
    assert frozen["outstanding_right_base_units"] == "25000000"
    assert frozen["excess_refundable_base_units"] == "60000000"
    assert frozen["request_snapshot_hash"] == at_request["request_snapshot_hash"]


def test_claim_deadline_is_exclusive() -> None:
    assert activation_is_eligible(
        now=DEADLINE - timedelta(seconds=1), claim_deadline="2026-08-01T00:06:00Z"
    )
    assert not activation_is_eligible(now=DEADLINE, claim_deadline="2026-08-01T00:06:00Z")
    assert not activation_is_eligible(
        now=DEADLINE + timedelta(seconds=1), claim_deadline="2026-08-01T00:06:00Z"
    )


def test_close_rejects_short_grace_and_freeze_before_deadline() -> None:
    assert_error(
        "close_grace_too_short",
        lambda: request_close(
            channel(),
            closure_id="closure_short",
            idempotency_key="close_short",
            now=NOW,
            claim_deadline=NOW + timedelta(seconds=59),
        ),
    )
    artifacts = request_close(
        channel(),
        closure_id="closure_001",
        idempotency_key="close_001",
        now=NOW,
        claim_deadline=DEADLINE,
    )
    assert_error(
        "claim_window_open",
        lambda: freeze_closure(
            artifacts.request,
            artifacts.snapshot_at_request,
            channel(
                status="closing",
                activated=40_000_000,
                settled=15_000_000,
                latest_sequence=3,
                updated_at="2026-08-01T00:05:59Z",
            ),
            now=DEADLINE - timedelta(seconds=1),
        ),
    )


def test_activated_right_survives_time_and_remains_reserved() -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(
        request,
        frozen,
        amount=60_000_000,
        expires_in=timedelta(days=31),
    )
    projection = project_refund(intent, frozen, now=DEADLINE + timedelta(days=30))

    assert projection["activated_total_base_units"] == "40000000"
    assert projection["outstanding_right_base_units"] == "25000000"
    assert projection["maximum_refundable_base_units"] == "60000000"


@pytest.mark.parametrize(
    "states",
    [
        ("submitted",),
        ("confirming",),
        ("reconciling",),
        ("needs_recovery",),
        ("needs_review",),
        ("disputed",),
    ],
)
def test_any_ambiguous_economic_state_blocks_refund(states: tuple[str, ...]) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    assert_error(
        "unresolved_economic_operation",
        lambda: project_refund(intent, frozen, now=DEADLINE, operation_states=states),
    )


def test_freeze_with_unresolved_operation_blocks_refund_even_without_runtime_state() -> None:
    _, request, _, frozen = closure_flow(operation_states=("needs_recovery",))
    intent = refund_request(request, frozen)
    assert frozen["unresolved_operation_count"] == 1
    assert_error(
        "unresolved_economic_operation",
        lambda: project_refund(intent, frozen, now=DEADLINE),
    )


def test_refund_bounds_and_final_close_right_gate() -> None:
    _, request, _, frozen = closure_flow()
    assert_error(
        "refund_exceeds_unallocated",
        lambda: project_refund(
            refund_request(request, frozen, amount=60_000_001),
            frozen,
            now=DEADLINE,
        ),
    )
    assert_error(
        "outstanding_right_reserved",
        lambda: project_refund(
            refund_request(request, frozen, amount=60_000_000, reason="final_close"),
            frozen,
            now=DEADLINE,
        ),
    )
    assert_error(
        "amount_must_be_positive",
        lambda: make_refund_request(
            request,
            frozen,
            refund_id="refund_zero",
            idempotency_key="refund_zero",
            reason="post_claim_window_unallocated",
            requested_base_units=0,
            now=DEADLINE,
            expires_at=DEADLINE + timedelta(minutes=1),
        ),
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"destination": VAULT}, "refund_destination_substitution"),
        (
            {"channel": {"channel_id": "channel_other"}},
            "channel_reference_mismatch",
        ),
        ({"channel": {"epoch": 1}}, "channel_reference_mismatch"),
        ({"channel": {"mint": VAULT}}, "channel_reference_mismatch"),
        ({"domain": {"network": "solana:mainnet"}}, "domain_mismatch"),
        (
            {"freeze_snapshot_hash": "sha256:" + ("9" * 64)},
            "freeze_snapshot_mismatch",
        ),
    ],
)
def test_refund_rejects_domain_identity_and_snapshot_replay(
    mutation: dict,
    expected_code: str,
) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    changed = copy.deepcopy(intent)
    for field, value in mutation.items():
        if isinstance(value, dict):
            changed[field].update(value)
        else:
            changed[field] = value
    changed = rehash(changed, "request_hash")

    assert_error(
        expected_code,
        lambda: project_refund(changed, frozen, now=DEADLINE),
    )


def test_expired_refund_and_tampered_artifacts_fail_closed() -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    assert_error(
        "refund_request_expired",
        lambda: project_refund(
            intent,
            frozen,
            now=DEADLINE + timedelta(minutes=5),
        ),
    )
    tampered = {**intent, "requested_base_units": "1"}
    assert_error(
        "artifact_tampering",
        lambda: project_refund(tampered, frozen, now=DEADLINE),
    )
    inconsistent_freeze = rehash(
        {**frozen, "vault_balance_base_units": "1"},
        "freeze_snapshot_hash",
    )
    assert_error(
        "conservation_violation",
        lambda: project_refund(intent, inconsistent_freeze, now=DEADLINE),
    )


def test_golden_refund_preserves_conservation_without_reducing_activation() -> None:
    _, request, _, frozen = closure_flow()
    projection = project_refund(
        refund_request(request, frozen),
        frozen,
        now=DEADLINE,
    )

    assert projection["activated_total_base_units"] == "40000000"
    assert projection["refunded_total_after_base_units"] == "60000000"
    assert projection["vault_balance_after_base_units"] == "25000000"
    assert 100_000_000 == 25_000_000 + 15_000_000 + 60_000_000


def test_finalization_requires_no_right_no_vault_and_no_ambiguity() -> None:
    outstanding = channel(
        status="closing",
        activated=40_000_000,
        settled=15_000_000,
        refunded=60_000_000,
        latest_sequence=3,
        updated_at="2026-08-01T00:06:00Z",
    )
    assert_error(
        "outstanding_right_reserved",
        lambda: validate_finalization(outstanding, now=DEADLINE),
    )
    eligible = channel(
        status="closing",
        activated=40_000_000,
        settled=40_000_000,
        refunded=60_000_000,
        latest_sequence=3,
        updated_at="2026-08-01T00:06:00Z",
    )
    validate_finalization(eligible, now=DEADLINE)
    assert_error(
        "unresolved_economic_operation",
        lambda: validate_finalization(
            eligible,
            now=DEADLINE,
            operation_states=("reconciling",),
        ),
    )


def test_runtime_idempotency_restart_and_changed_bytes(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    path = tmp_path / "closure.sqlite3"
    first = ClosureRuntime(path).register_refund(intent, frozen, now=DEADLINE)
    second = ClosureRuntime(path).register_refund(intent, frozen, now=DEADLINE)

    assert first.refund_id == second.refund_id
    changed = rehash({**intent, "requested_base_units": "1"}, "request_hash")
    assert_error(
        "idempotency_conflict",
        lambda: ClosureRuntime(path).register_refund(changed, frozen, now=DEADLINE),
    )


def test_two_process_style_race_cannot_over_refund(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    path = tmp_path / "race.sqlite3"
    requests = [
        refund_request(request, frozen, amount=40_000_000, suffix="a"),
        refund_request(request, frozen, amount=40_000_000, suffix="b"),
    ]

    def register(value: dict) -> str:
        try:
            return ClosureRuntime(path).register_refund(value, frozen, now=DEADLINE).state
        except ClosureError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, requests))

    assert sorted(results) == ["aggregate_refund_exceeds_unallocated", "validated"]


def test_submit_intent_is_at_most_one_and_unknown_never_completes(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    runtime = ClosureRuntime(tmp_path / "unknown.sqlite3")
    runtime.register_refund(intent, frozen, now=DEADLINE)
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    record = runtime.record_technical_receipt(
        intent["refund_id"],
        technical_receipt(intent, outcome="unknown"),
        now=DEADLINE + timedelta(seconds=5),
    )

    assert record.state == "needs_recovery"
    assert record.submit_intent_count == 1
    assert record.reconciled_receipt is None


def test_technical_receipt_is_not_economic_completion(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    runtime = ClosureRuntime(tmp_path / "technical.sqlite3")
    registered = runtime.register_refund(intent, frozen, now=DEADLINE)
    projection = json.loads(sqlite_projection(runtime.path, registered.refund_id))
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    technical = runtime.record_technical_receipt(
        intent["refund_id"],
        technical_receipt(intent),
        now=DEADLINE + timedelta(seconds=5),
    )

    assert technical.state == "reconciling"
    assert technical.reconciled_receipt is None
    completed = runtime.reconcile(
        intent["refund_id"],
        refund_observation(intent, projection),
        observation_verifier=FixtureObservationVerifier(),
        now=DEADLINE + timedelta(seconds=10),
    )
    assert completed.state == "completed"
    assert completed.reconciled_receipt is not None
    assert completed.reconciled_receipt["refunded_total_after_base_units"] == "60000000"


def sqlite_projection(path: Path, refund_id: str) -> str:
    import sqlite3

    connection = sqlite3.connect(path)
    try:
        return str(
            connection.execute(
                "SELECT projection_json FROM refunds WHERE refund_id = ?",
                (refund_id,),
            ).fetchone()[0]
        )
    finally:
        connection.close()


def test_reconciliation_mismatch_never_completes(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    runtime = ClosureRuntime(tmp_path / "mismatch.sqlite3")
    runtime.register_refund(intent, frozen, now=DEADLINE)
    projection = json.loads(sqlite_projection(runtime.path, intent["refund_id"]))
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    runtime.record_technical_receipt(
        intent["refund_id"],
        technical_receipt(intent),
        now=DEADLINE + timedelta(seconds=5),
    )
    mismatched = refund_observation(
        intent,
        projection,
        vault_balance_after_base_units="25000001",
    )

    assert_error(
        "reconciliation_mismatch",
        lambda: runtime.reconcile(
            intent["refund_id"],
            mismatched,
            observation_verifier=FixtureObservationVerifier(),
            now=DEADLINE + timedelta(seconds=10),
        ),
    )
    assert runtime.get(intent["refund_id"]).state == "needs_review"


def test_pre_submission_release_frees_reservation(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    runtime = ClosureRuntime(tmp_path / "release.sqlite3")
    first = refund_request(request, frozen, amount=60_000_000, suffix="first")
    second = refund_request(request, frozen, amount=60_000_000, suffix="second")
    runtime.register_refund(first, frozen, now=DEADLINE)
    runtime.release_before_submission(
        first["refund_id"],
        state="explicitly_cancelled_before_authorization",
        now=DEADLINE,
    )

    assert runtime.register_refund(second, frozen, now=DEADLINE).state == "validated"


def test_lost_response_restart_recovers_signature_without_second_submit(tmp_path: Path) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    path = tmp_path / "recovery.sqlite3"
    runtime = ClosureRuntime(path)
    runtime.register_refund(intent, frozen, now=DEADLINE)
    projection = json.loads(sqlite_projection(path, intent["refund_id"]))
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    runtime.record_technical_receipt(
        intent["refund_id"],
        technical_receipt(intent, outcome="unknown"),
        now=DEADLINE + timedelta(seconds=5),
    )

    restarted = ClosureRuntime(path)
    recovered = restarted.record_recovered_signature(
        intent["refund_id"],
        transaction_signature=SIGNATURE,
        status_response_hash="sha256:" + ("d" * 64),
        now=DEADLINE + timedelta(seconds=8),
    )
    repeated = restarted.record_recovered_signature(
        intent["refund_id"],
        transaction_signature=SIGNATURE,
        status_response_hash="sha256:" + ("d" * 64),
        now=DEADLINE + timedelta(seconds=9),
    )
    completed = restarted.reconcile(
        intent["refund_id"],
        refund_observation(intent, projection),
        observation_verifier=FixtureObservationVerifier(),
        now=DEADLINE + timedelta(seconds=10),
    )

    assert recovered.state == repeated.state == "reconciling"
    assert completed.state == "completed"
    assert completed.submit_intent_count == 1


def test_provider_divergence_is_disputed_and_unverified_observation_fails(
    tmp_path: Path,
) -> None:
    _, request, _, frozen = closure_flow()
    intent = refund_request(request, frozen)
    runtime = ClosureRuntime(tmp_path / "divergence.sqlite3")
    runtime.register_refund(intent, frozen, now=DEADLINE)
    projection = json.loads(sqlite_projection(runtime.path, intent["refund_id"]))
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    runtime.record_technical_receipt(
        intent["refund_id"],
        technical_receipt(intent),
        now=DEADLINE + timedelta(seconds=5),
    )
    assert_error(
        "observation_unverified",
        lambda: runtime.reconcile(
            intent["refund_id"],
            refund_observation(intent, projection),
            observation_verifier=FixtureObservationVerifier(accepted=False),
            now=DEADLINE + timedelta(seconds=6),
        ),
    )
    disputed = runtime.record_provider_divergence(
        intent["refund_id"],
        provider_ids=("provider_a", "provider_b"),
        now=DEADLINE + timedelta(seconds=7),
    )
    assert disputed.state == "disputed"


def test_epoch_eligibility_is_only_a_decision_and_binds_final_hash() -> None:
    closed = channel(
        status="closed",
        activated=40_000_000,
        settled=40_000_000,
        refunded=60_000_000,
        latest_sequence=3,
        updated_at="2026-08-01T00:06:00Z",
    )
    result = epoch_transition_eligibility(
        closed,
        previous_final_closure_hash="sha256:" + ("f" * 64),
        unresolved_operation_count=0,
        now=DEADLINE,
    )

    assert result["decision"] == "epoch_transition_eligible"
    assert "executed" not in json.dumps(result)
    assert result["next_epoch"] == 1
    assert result["next_latest_voucher_hash"] == "sha256:" + ("0" * 64)
    assert_error(
        "unresolved_economic_operation",
        lambda: epoch_transition_eligibility(
            closed,
            previous_final_closure_hash="sha256:" + ("f" * 64),
            unresolved_operation_count=1,
            now=DEADLINE,
        ),
    )


def test_schema_accepts_runtime_artifacts(tmp_path: Path) -> None:
    schema = json.loads(
        (ROOT / "contracts" / "channel" / "channel-closure.schema.json").read_text()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    _, request, at_request, frozen = closure_flow()
    intent = refund_request(request, frozen)
    projection = project_refund(intent, frozen, now=DEADLINE)
    runtime = ClosureRuntime(tmp_path / "schema.sqlite3")
    runtime.register_refund(intent, frozen, now=DEADLINE)
    runtime.record_submit_intent(intent["refund_id"], now=DEADLINE)
    tech = technical_receipt(intent)
    runtime.record_technical_receipt(
        intent["refund_id"],
        tech,
        now=DEADLINE + timedelta(seconds=5),
    )
    observation = refund_observation(intent, projection)
    completed = runtime.reconcile(
        intent["refund_id"],
        observation,
        observation_verifier=FixtureObservationVerifier(),
        now=DEADLINE + timedelta(seconds=10),
    )
    closed = channel(
        status="closed",
        activated=40_000_000,
        settled=40_000_000,
        refunded=60_000_000,
        latest_sequence=3,
        updated_at="2026-08-01T00:06:00Z",
    )
    eligibility = epoch_transition_eligibility(
        closed,
        previous_final_closure_hash="sha256:" + ("f" * 64),
        unresolved_operation_count=0,
        now=DEADLINE,
    )

    for artifact in (
        request,
        at_request,
        frozen,
        intent,
        projection,
        tech,
        observation,
        completed.reconciled_receipt,
        eligibility,
    ):
        errors = list(validator.iter_errors(artifact))
        assert not errors, [error.message for error in errors]
