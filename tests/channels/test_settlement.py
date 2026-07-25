"""FC-PROTO-004 offline settlement, recovery, and reconciliation tests."""

from __future__ import annotations

import copy
import ast
import json
import sqlite3
import sys
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages" / "channel-protocol" / "python"))
sys.path.insert(0, str(ROOT / "packages" / "external-execution-protocol" / "python"))

from foundry_channel_protocol import (  # noqa: E402
    DefinitiveExecutorRejection,
    SettlementError,
    SettlementRuntime,
    channel_snapshot_hash,
    validate_settlement_request,
)
from foundry_external_execution_protocol import (  # noqa: E402
    FakeAuthorizationAuthority,
    FakeExternalExecutor,
    economic_plan_hash,
    sha256_digest,
)
from foundry_external_execution_protocol.canonicalization import canonicalize  # noqa: E402


NOW = datetime(2026, 8, 1, 0, 6, 10, tzinfo=UTC)
GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
PROGRAM = "BPFLoaderUpgradeab1e11111111111111111111111"
CHANNEL_ACCOUNT = "EUt7wV4f5bzSFJccZ5aafJV7zykZfyWz9rctaug7hVxd"
SENDER = "9zsJvRFTxAG5sBuXhjMDZkgWb9oqQbK8gDywo7mUMNKb"
CLAIM_KEY = "9LAfXjiLxADaSQw2ipGQq5kPyzCy8F2hZhnP4YLBEReV"
MINT = "2tUzxADKHWxwTpihHuuzwfoGhYBY7735s2QXEuUcNX3k"
DESTINATION = "6dz2u59pmn9JnSMQMeB16Mq2iMDzx3Jz1Xa2dTdbxAiE"
VAULT = "11111111111111111111111111111111"
SIGNER = VAULT
AUTHORITY_KEY = b"fc-proto-004-synthetic-authority-key"


def snapshot(
    *,
    activated: int = 40_000_000,
    settled: int = 15_000_000,
    funded: int = 100_000_000,
    recipient_wallet: str = DESTINATION,
) -> dict:
    return {
        "type": "channel",
        "protocol_version": "1.0.0",
        "account_version": 1,
        "environment": "devnet",
        "network": "solana:devnet",
        "genesis_hash": GENESIS,
        "program_id": PROGRAM,
        "channel_id": "channel_settlement_001",
        "channel_account": CHANNEL_ACCOUNT,
        "epoch": 0,
        "sender": SENDER,
        "recipient_claim_pubkey": CLAIM_KEY,
        "recipient_wallet": recipient_wallet,
        "mint": MINT,
        "decimals": 6,
        "vault_token_account": VAULT,
        "funded_total_base_units": str(funded),
        "activated_authorized_total_base_units": str(activated),
        "settled_total_base_units": str(settled),
        "refunded_total_base_units": "0",
        "latest_activated_sequence": 3,
        "latest_activated_voucher_hash": "sha256:" + ("a" * 64),
        "status": "active",
        "expires_at": "2026-08-03T00:00:00Z",
        "policy": {
            "type": "channel_policy",
            "protocol_version": "1.0.0",
            "channel_id": "channel_settlement_001",
            "max_cumulative_authorized_base_units": "100000000",
            "allow_partial_settlement": True,
            "allow_top_up": True,
            "minimum_close_grace_seconds": 86400,
            "rebind_mode": "disabled",
        },
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:06:00Z",
    }


def request(
    channel: dict,
    *,
    requested: int = 20_000_000,
    suffix: str = "001",
    idempotency_key: str | None = None,
) -> dict:
    funded = int(channel["funded_total_base_units"])
    settled = int(channel["settled_total_base_units"])
    refunded = int(channel["refunded_total_base_units"])
    return {
        "type": "settlement_request",
        "protocol_version": "1.0.0",
        "environment": channel["environment"],
        "network": channel["network"],
        "genesis_hash": channel["genesis_hash"],
        "program_id": channel["program_id"],
        "channel_id": channel["channel_id"],
        "channel_account": channel["channel_account"],
        "epoch": channel["epoch"],
        "mint": channel["mint"],
        "recipient_wallet": channel["recipient_wallet"],
        "settlement_id": f"settlement_{suffix}",
        "execution_request_id": f"execution_{suffix}",
        "obligation_id": f"obligation_{suffix}",
        "idempotency_key": idempotency_key or f"idempotency_{suffix}",
        "requested_base_units": str(requested),
        "activated_total_before": channel["activated_authorized_total_base_units"],
        "settled_total_before": channel["settled_total_base_units"],
        "vault_balance_before": str(funded - settled - refunded),
        "channel_snapshot_hash": channel_snapshot_hash(channel),
        "created_at": "2026-08-01T00:06:00Z",
        "expires_at": "2026-08-01T00:10:00Z",
    }


def simulation() -> dict:
    return {
        "rpc_provider_id": "offline-fixture",
        "genesis_hash": GENESIS,
        "slot": 123,
        "commitment_level": "confirmed",
        "recent_blockhash": "b" * 32,
        "last_valid_block_height": 456,
        "simulated_at": "2026-08-01T00:06:05Z",
        "valid_until": "2026-08-01T00:09:00Z",
        "logs_hash": "sha256:" + ("b" * 64),
        "pre_balances_hash": "sha256:" + ("c" * 64),
        "post_balances_hash": "sha256:" + ("d" * 64),
        "units_consumed": 1200,
        "fee_lamports": 5000,
        "success": True,
    }


def economic_approval(settlement_request: dict, channel: dict) -> dict:
    plan = {
        "protocol_version": "1.0.0",
        "normalization_profile": "foundry-pay-domain-v1",
        "obligation_id": settlement_request["obligation_id"],
        "network": settlement_request["network"],
        "capability": "solana.spl_transfer.v1",
        "asset": {"kind": "spl-token", "mint": MINT, "decimals": 6},
        "amount_base_units": settlement_request["requested_base_units"],
        "source": channel["vault_token_account"],
        "destination": settlement_request["recipient_wallet"],
        "expires_at": settlement_request["expires_at"],
    }
    return {
        "approval_id": f"approval_{settlement_request['settlement_id']}",
        "economic_plan_hash": economic_plan_hash(plan),
        "approved_by": "offline_protocol_test",
        "issued_at": "2026-08-01T00:06:00Z",
        "expires_at": "2026-08-01T00:09:00Z",
    }


def prepared_flow(
    tmp_path: Path,
    *,
    requested: int = 20_000_000,
    suffix: str = "001",
) -> tuple[
    SettlementRuntime,
    FakeExternalExecutor,
    FakeAuthorizationAuthority,
    dict,
    dict,
    dict,
]:
    channel = snapshot()
    settlement_request = request(channel, requested=requested, suffix=suffix)
    runtime = SettlementRuntime(tmp_path / f"runtime-{suffix}.sqlite3")
    runtime.register_request(settlement_request, channel_snapshot=channel, now=NOW)
    authority = FakeAuthorizationAuthority(AUTHORITY_KEY)
    executor = FakeExternalExecutor(
        tmp_path / f"executor-{suffix}.sqlite3",
        authorization_authority=authority,
    )
    external_request = runtime.external_execution_request(
        settlement_request["settlement_id"],
        economic_approval=economic_approval(settlement_request, channel),
    )
    prepared = executor.prepare(
        external_request,
        simulation=simulation(),
        signer=SIGNER,
        constraints={
            "max_fee_lamports": 50_000,
            "allowed_programs": [PROGRAM],
        },
        expires_at="2026-08-01T00:08:00Z",
        now=NOW,
    )
    runtime.commit_execution(
        settlement_request["settlement_id"],
        prepared,
        expected_signer=SIGNER,
        now=NOW,
    )
    authorization = authority.issue(
        prepared,
        authorization_id=f"authorization_{suffix}",
        issued_at="2026-08-01T00:06:00Z",
        expires_at="2026-08-01T00:07:00Z",
    )
    runtime.record_authorization(
        settlement_request["settlement_id"],
        authorization,
        verifier=authority,
        now=NOW,
    )
    return runtime, executor, authority, channel, settlement_request, prepared


def observation(
    settlement_request: dict,
    signature: str,
    *,
    source_id: str = "observer_a",
    settled_after: int | None = None,
    vault_after: int | None = None,
    recipient_delta: int | None = None,
    destination: str = DESTINATION,
) -> dict:
    requested = int(settlement_request["requested_base_units"])
    settled_before = int(settlement_request["settled_total_before"])
    vault_before = int(settlement_request["vault_balance_before"])
    unsigned = {
        "type": "settlement_observation",
        "protocol_version": "1.0.0",
        "source_id": source_id,
        "channel_id": settlement_request["channel_id"],
        "channel_account": settlement_request["channel_account"],
        "epoch": settlement_request["epoch"],
        "mint": settlement_request["mint"],
        "destination": destination,
        "transaction_signature": signature,
        "settled_total_before": str(settled_before),
        "settled_total_after": str(
            settled_before + requested if settled_after is None else settled_after
        ),
        "vault_balance_before": str(vault_before),
        "vault_balance_after": str(
            vault_before - requested if vault_after is None else vault_after
        ),
        "recipient_balance_before": "5000000",
        "recipient_balance_after": str(
            5_000_000 + (requested if recipient_delta is None else recipient_delta)
        ),
        "observed_at": "2026-08-01T00:07:00Z",
    }
    return {
        **unsigned,
        "observation_hash": sha256_digest(canonicalize(unsigned)),
    }


class ExactObservationVerifier:
    """Test-only independent boundary pinned to one exact provider artifact."""

    def __init__(self, value: dict) -> None:
        self.source_id = value["source_id"]
        self.expected_hash = value["observation_hash"]

    def verify(self, value: Mapping[str, object]) -> bool:
        return (
            value["source_id"] == self.source_id and value["observation_hash"] == self.expected_hash
        )


def observation_verifiers(*values: dict) -> dict[str, ExactObservationVerifier]:
    return {value["source_id"]: ExactObservationVerifier(value) for value in values}


def assert_error(code: str, function, *args, **kwargs) -> SettlementError:
    with pytest.raises(SettlementError) as captured:
        function(*args, **kwargs)
    assert captured.value.code == code
    return captured.value


def test_partial_and_full_settlement_requests_validate() -> None:
    channel = snapshot()
    partial = validate_settlement_request(
        request(channel, requested=20_000_000),
        channel_snapshot=channel,
        now=NOW,
    )
    full = validate_settlement_request(
        request(channel, requested=25_000_000, suffix="full"),
        channel_snapshot=channel,
        now=NOW,
    )
    assert partial.requested_base_units == 20_000_000
    assert full.requested_base_units == 25_000_000


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ({"requested_base_units": "0"}, "zero_settlement"),
        ({"requested_base_units": "25000001"}, "over_settlement"),
        ({"recipient_wallet": SENDER}, "snapshot_context_mismatch"),
        ({"channel_id": "other_channel"}, "snapshot_context_mismatch"),
        ({"epoch": 1}, "snapshot_context_mismatch"),
        ({"mint": SENDER}, "snapshot_context_mismatch"),
        ({"expires_at": "2026-08-01T00:06:10Z"}, "request_expired"),
        ({"expires_at": "2026-08-04T00:00:00Z"}, "request_outlives_channel"),
        ({"channel_snapshot_hash": "sha256:" + ("f" * 64)}, "snapshot_tampering"),
    ],
)
def test_request_tampering_and_bounds_reject(mutation: dict, code: str) -> None:
    channel = snapshot()
    value = request(channel)
    value.update(mutation)
    assert_error(
        code,
        validate_settlement_request,
        value,
        channel_snapshot=channel,
        now=NOW,
    )


def test_settlement_above_vault_rejects_even_with_larger_activated_total() -> None:
    channel = snapshot(activated=100_000_000, settled=95_000_000, funded=100_000_000)
    value = request(channel, requested=5_000_001)
    assert_error(
        "over_settlement",
        validate_settlement_request,
        value,
        channel_snapshot=channel,
        now=NOW,
    )


def test_duplicate_request_is_idempotent_but_changed_bytes_conflict(tmp_path: Path) -> None:
    runtime = SettlementRuntime(tmp_path / "runtime.sqlite3")
    channel = snapshot()
    value = request(channel)
    first = runtime.register_request(value, channel_snapshot=channel, now=NOW)
    repeated = runtime.register_request(value, channel_snapshot=channel, now=NOW)
    assert repeated.request_hash == first.request_hash
    changed = copy.deepcopy(value)
    changed["requested_base_units"] = "19000000"
    assert_error(
        "idempotency_conflict",
        runtime.register_request,
        changed,
        channel_snapshot=channel,
        now=NOW,
    )


def test_two_process_same_request_create_one_logical_record(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite3"
    channel = snapshot()
    value = request(channel)

    def register() -> str:
        return (
            SettlementRuntime(path)
            .register_request(
                value,
                channel_snapshot=channel,
                now=NOW,
            )
            .request_hash
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        hashes = list(pool.map(lambda _: register(), range(2)))
    assert len(set(hashes)) == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 1


def test_two_process_same_key_different_requests_conflict(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite3"
    channel = snapshot()
    values = [
        request(
            channel,
            requested=10_000_000 + index,
            suffix=str(index),
            idempotency_key="same_key",
        )
        for index in range(2)
    ]

    def register(value: dict) -> str:
        try:
            SettlementRuntime(path).register_request(value, channel_snapshot=channel, now=NOW)
            return "accepted"
        except SettlementError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(register, values))
    assert outcomes == ["accepted", "idempotency_conflict"]


def test_concurrent_partial_reservations_cannot_exceed_activated_right(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.sqlite3"
    channel = snapshot()
    requests = [
        request(channel, requested=20_000_000, suffix="a"),
        request(channel, requested=20_000_000, suffix="b"),
    ]

    def register(value: dict) -> str:
        try:
            SettlementRuntime(path).register_request(value, channel_snapshot=channel, now=NOW)
            return "accepted"
        except SettlementError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(register, requests))
    assert outcomes == ["accepted", "concurrent_over_settlement"]


def test_full_and_partial_concurrent_reservations_preserve_aggregate_bound(
    tmp_path: Path,
) -> None:
    runtime = SettlementRuntime(tmp_path / "runtime.sqlite3")
    channel = snapshot()
    runtime.register_request(
        request(channel, requested=25_000_000, suffix="full"),
        channel_snapshot=channel,
        now=NOW,
    )
    assert_error(
        "concurrent_over_settlement",
        runtime.register_request,
        request(channel, requested=1, suffix="partial"),
        channel_snapshot=channel,
        now=NOW,
    )


def test_exact_execution_commitment_and_authorization_are_persisted(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, settlement_request, prepared = prepared_flow(tmp_path)
    record = runtime.get(settlement_request["settlement_id"])
    assert record.state == "authorized"
    events = runtime.journal(settlement_request["settlement_id"])
    assert [event.state for event in events] == [
        "requested",
        "validated",
        "execution_committed",
        "authorized",
    ]
    commitment_event = events[2]
    assert commitment_event.previous_event_hash == events[1].event_hash
    assert prepared["prepared_message_hash"] in json.dumps([event.to_dict() for event in events])


def test_commitment_tampering_and_wrong_signer_reject(tmp_path: Path) -> None:
    channel = snapshot()
    settlement_request = request(channel)
    runtime = SettlementRuntime(tmp_path / "runtime.sqlite3")
    runtime.register_request(settlement_request, channel_snapshot=channel, now=NOW)
    authority = FakeAuthorizationAuthority(AUTHORITY_KEY)
    executor = FakeExternalExecutor(
        tmp_path / "executor.sqlite3",
        authorization_authority=authority,
    )
    external = runtime.external_execution_request(
        settlement_request["settlement_id"],
        economic_approval=economic_approval(settlement_request, channel),
    )
    prepared = executor.prepare(
        external,
        simulation=simulation(),
        signer=SIGNER,
        constraints={"max_fee_lamports": 50_000, "allowed_programs": [PROGRAM]},
        expires_at="2026-08-01T00:08:00Z",
        now=NOW,
    )
    tampered = copy.deepcopy(prepared)
    tampered["economic_plan_hash"] = "sha256:" + ("f" * 64)
    assert_error(
        "economic_plan_mismatch",
        runtime.commit_execution,
        settlement_request["settlement_id"],
        tampered,
        expected_signer=SIGNER,
        now=NOW,
    )
    altered_bytes = copy.deepcopy(prepared)
    altered_bytes["prepared_message_base64"] = (
        altered_bytes["prepared_message_base64"][:-4] + "AAAA"
    )
    assert_error(
        "prepared_message_tampering",
        runtime.commit_execution,
        settlement_request["settlement_id"],
        altered_bytes,
        expected_signer=SIGNER,
        now=NOW,
    )
    altered_simulation = copy.deepcopy(prepared)
    altered_simulation["simulation"]["fee_lamports"] += 1
    assert_error(
        "simulation_tampering",
        runtime.commit_execution,
        settlement_request["settlement_id"],
        altered_simulation,
        expected_signer=SIGNER,
        now=NOW,
    )
    altered_commitment = copy.deepcopy(prepared)
    altered_commitment["execution_commitment_hash"] = "sha256:" + ("e" * 64)
    assert_error(
        "execution_commitment_tampering",
        runtime.commit_execution,
        settlement_request["settlement_id"],
        altered_commitment,
        expected_signer=SIGNER,
        now=NOW,
    )
    assert_error(
        "signer_mismatch",
        runtime.commit_execution,
        settlement_request["settlement_id"],
        prepared,
        expected_signer=SENDER,
        now=NOW,
    )


def test_technical_confirmation_is_not_economic_completion(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW + timedelta(seconds=10),
    )
    assert technical.outcome == "accepted"
    assert technical.technical_status == "confirmed"
    assert "payment_completed" not in json.dumps(technical.to_dict())
    assert "economically_settled" not in json.dumps(technical.to_dict())
    assert "business_success" not in json.dumps(technical.to_dict())
    record = runtime.get(settlement_request["settlement_id"])
    assert record.state == "reconciling"
    assert record.reconciled_receipt is None
    assert runtime.submit_intent_count(settlement_request["settlement_id"]) == 1


class TamperingExecutor:
    def __init__(self, delegate: FakeExternalExecutor) -> None:
        self.delegate = delegate
        self.executor_id = delegate.executor_id

    def authorize_and_execute(self, authorization, *, now, fault=None):
        receipt = dict(self.delegate.authorize_and_execute(authorization, now=now, fault=fault))
        receipt["prepared_message_hash"] = "sha256:" + ("f" * 64)
        return receipt

    def recover(self, execution_request_id, *, observed_at):
        return self.delegate.recover(execution_request_id, observed_at=observed_at)


def test_tampered_technical_receipt_never_completes(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    assert_error(
        "technical_receipt_tampering",
        runtime.submit,
        settlement_request["settlement_id"],
        executor=TamperingExecutor(executor),
        now=NOW + timedelta(seconds=10),
    )
    assert runtime.submit_intent_count(settlement_request["settlement_id"]) == 1
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_review"


class RejectingExecutor:
    executor_id = "fake-solana-executor"

    def authorize_and_execute(self, authorization, *, now, fault=None):
        raise DefinitiveExecutorRejection("policy_rejected")

    def recover(self, execution_request_id, *, observed_at):
        raise AssertionError("definitive pre-acceptance rejection does not need recovery")


def test_definitive_executor_rejection_is_not_unknown(tmp_path: Path) -> None:
    runtime, _, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=RejectingExecutor(),
        now=NOW,
    )
    assert technical.outcome == "rejected"
    assert technical.technical_status == "policy_rejected"
    assert runtime.get(settlement_request["settlement_id"]).state == "rejected"
    assert runtime.submit_intent_count(settlement_request["settlement_id"]) == 1


def test_lost_response_restart_recovers_signature_without_second_submit(
    tmp_path: Path,
) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW + timedelta(seconds=10),
        fault="after_commit_before_response",
    )
    assert technical.outcome == "unknown"
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_recovery"

    restarted = SettlementRuntime(runtime.path)
    assert_error(
        "submission_already_attempted",
        restarted.submit,
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW + timedelta(seconds=20),
    )
    recovered = restarted.recover(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW + timedelta(seconds=20),
    )
    assert recovered.outcome == "confirmed"
    assert recovered.submit_intent_count == 1
    assert recovered.automatic_second_submission_count == 0
    assert recovered.transaction_signature
    assert recovered.executor_id == executor.executor_id
    expected_status = executor.recover(
        settlement_request["execution_request_id"],
        observed_at=NOW + timedelta(seconds=20),
    )
    assert recovered.status_response_hash == sha256_digest(canonicalize(expected_status))
    assert restarted.get(settlement_request["settlement_id"]).state == "reconciling"

    supplied = observation(settlement_request, recovered.transaction_signature)
    receipt = restarted.reconcile(
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW + timedelta(seconds=30),
    )
    assert receipt is not None
    assert receipt.settled_total_after == 35_000_000
    assert restarted.submit_intent_count(settlement_request["settlement_id"]) == 1
    assert executor.effect_count(settlement_request["obligation_id"]) == 1


class UnknownRecoveryExecutor:
    executor_id = "fake-solana-executor"

    def authorize_and_execute(self, authorization, *, now, fault=None):
        raise TimeoutError("synthetic lost response")

    def recover(self, execution_request_id, *, observed_at):
        return {
            "type": "recovery_result",
            "protocol_version": "1.0.0",
            "execution_request_id": execution_request_id,
            "outcome": "unknown",
            "may_rematerialize": False,
            "observed_at": observed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


class FabricatedRecoveryExecutor:
    executor_id = "fake-solana-executor"

    def __init__(self, *, execution_request_id: str) -> None:
        self.execution_request_id = execution_request_id

    def recover(self, execution_request_id, *, observed_at):
        return {
            "type": "recovery_result",
            "protocol_version": "1.0.0",
            "execution_request_id": self.execution_request_id,
            "outcome": "confirmed",
            "may_rematerialize": False,
            "observed_at": observed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "transaction_signature": "fabricated_signature",
        }


class WrongExecutorIdentity(FabricatedRecoveryExecutor):
    executor_id = "different-executor"


def test_unknown_and_repeated_recovery_remain_blocked(tmp_path: Path) -> None:
    runtime, _, _, _, settlement_request, _ = prepared_flow(tmp_path)
    executor = UnknownRecoveryExecutor()
    runtime.submit(settlement_request["settlement_id"], executor=executor, now=NOW)
    first = runtime.recover(settlement_request["settlement_id"], executor=executor, now=NOW)
    second = runtime.recover(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW + timedelta(seconds=1),
    )
    assert first.outcome == second.outcome == "unknown"
    assert first.submit_intent_count == second.submit_intent_count == 1
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_recovery"

    retry = copy.deepcopy(settlement_request)
    retry["settlement_id"] = "settlement_retry"
    retry["execution_request_id"] = "execution_retry"
    retry["idempotency_key"] = "idempotency_retry"
    assert_error(
        "obligation_needs_recovery",
        runtime.register_request,
        retry,
        channel_snapshot=snapshot(),
        now=NOW,
    )


def test_recovery_rejects_executor_not_bound_by_commitment(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
        fault="after_commit_before_response",
    )
    attacker = WrongExecutorIdentity(
        execution_request_id=settlement_request["execution_request_id"],
    )
    assert_error(
        "executor_mismatch",
        runtime.recover,
        settlement_request["settlement_id"],
        executor=attacker,
        now=NOW + timedelta(seconds=1),
    )
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_recovery"


def test_recovery_rejects_uncorrelated_status_response(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
        fault="after_commit_before_response",
    )
    attacker = FabricatedRecoveryExecutor(execution_request_id="execution_other")
    assert_error(
        "recovery_request_mismatch",
        runtime.recover,
        settlement_request["settlement_id"],
        executor=attacker,
        now=NOW + timedelta(seconds=1),
    )
    record = runtime.recovery_records(settlement_request["settlement_id"])[-1]
    assert record.outcome == "invalid_status_response"
    assert record.detail == {
        "validation_code": "recovery_request_mismatch",
        "validation_field": "recovery_result.execution_request_id",
    }
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_review"


def test_provider_divergence_is_disputed(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    runtime.submit(settlement_request["settlement_id"], executor=executor, now=NOW)
    recovery = runtime.record_provider_divergence(
        settlement_request["settlement_id"],
        provider_ids=["provider_a", "provider_b"],
        now=NOW + timedelta(seconds=1),
    )
    assert recovery.outcome == "provider_divergence"
    assert recovery.detail == {"provider_ids": ["provider_a", "provider_b"]}
    serialized = recovery.to_dict()
    recovery_hash = serialized.pop("recovery_hash")
    assert sha256_digest(canonicalize(serialized)) == recovery_hash
    assert runtime.get(settlement_request["settlement_id"]).state == "disputed"


def test_disputed_settlement_keeps_economic_reservation(tmp_path: Path) -> None:
    runtime, executor, _, channel, settlement_request, _ = prepared_flow(tmp_path)
    runtime.submit(settlement_request["settlement_id"], executor=executor, now=NOW)
    runtime.record_provider_divergence(
        settlement_request["settlement_id"],
        provider_ids=["provider_a", "provider_b"],
        now=NOW + timedelta(seconds=1),
    )
    competing = request(channel, requested=20_000_000, suffix="competing")
    assert_error(
        "concurrent_over_settlement",
        runtime.register_request,
        competing,
        channel_snapshot=channel,
        now=NOW + timedelta(seconds=2),
    )


def test_reconciliation_requires_explicit_independent_verifier(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature)
    assert_error(
        "observation_verifier_missing",
        runtime.reconcile,
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers={},
        now=NOW + timedelta(seconds=1),
    )
    independently_rejected = observation(
        settlement_request,
        technical.transaction_signature,
        recipient_delta=19_999_999,
    )
    assert_error(
        "observation_unverified",
        runtime.reconcile,
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(independently_rejected),
        now=NOW + timedelta(seconds=1),
    )
    forged = copy.deepcopy(supplied)
    forged["observation_hash"] = "sha256:" + ("f" * 64)
    assert_error(
        "observation_tampering",
        runtime.reconcile,
        settlement_request["settlement_id"],
        [forged],
        observation_verifiers=observation_verifiers(forged),
        now=NOW + timedelta(seconds=1),
    )
    assert runtime.get(settlement_request["settlement_id"]).state == "reconciling"


@pytest.mark.parametrize(
    "changes",
    [
        {"settled_after": 34_999_999},
        {"vault_after": 65_000_001},
        {"recipient_delta": 19_999_999},
        {"destination": SENDER},
    ],
)
def test_reconciliation_mismatch_never_completes(
    tmp_path: Path,
    changes: dict,
) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature, **changes)
    result = runtime.reconcile(
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW + timedelta(seconds=1),
    )
    assert result is None
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_review"


def test_two_observation_providers_must_agree(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    first = observation(
        settlement_request,
        technical.transaction_signature,
        source_id="provider_a",
    )
    second = observation(
        settlement_request,
        technical.transaction_signature,
        source_id="provider_b",
        settled_after=34_999_999,
    )
    assert (
        runtime.reconcile(
            settlement_request["settlement_id"],
            [first, second],
            observation_verifiers=observation_verifiers(first, second),
            now=NOW + timedelta(seconds=1),
        )
        is None
    )
    assert runtime.get(settlement_request["settlement_id"]).state == "disputed"


def test_two_matching_observation_providers_can_reconcile(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = [
        observation(
            settlement_request,
            technical.transaction_signature,
            source_id=source,
        )
        for source in ("provider_a", "provider_b")
    ]
    supplied[1]["observed_at"] = "2026-08-01T00:07:01Z"
    unsigned = {key: child for key, child in supplied[1].items() if key != "observation_hash"}
    supplied[1]["observation_hash"] = sha256_digest(canonicalize(unsigned))
    receipt = runtime.reconcile(
        settlement_request["settlement_id"],
        supplied,
        observation_verifiers=observation_verifiers(*supplied),
        now=NOW + timedelta(seconds=1),
    )
    assert receipt is not None
    assert len(receipt.observation_hashes) == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("channel_id", "other_channel"),
        ("epoch", 1),
        ("mint", SENDER),
        ("transaction_signature", "different_signature"),
    ],
)
def test_reconciliation_context_substitution_never_completes(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature)
    supplied[field] = value
    unsigned = {key: child for key, child in supplied.items() if key != "observation_hash"}
    supplied["observation_hash"] = sha256_digest(canonicalize(unsigned))
    assert (
        runtime.reconcile(
            settlement_request["settlement_id"],
            [supplied],
            observation_verifiers=observation_verifiers(supplied),
            now=NOW + timedelta(seconds=1),
        )
        is None
    )
    assert runtime.get(settlement_request["settlement_id"]).state == "needs_review"


def test_successful_reconciliation_is_idempotent_and_hashed(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature)
    first = runtime.reconcile(
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW + timedelta(seconds=1),
    )
    repeated = runtime.reconcile(
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW + timedelta(seconds=2),
    )
    assert first == repeated
    assert first is not None
    assert first.receipt_hash.startswith("sha256:")
    assert runtime.get(settlement_request["settlement_id"]).state == "completed"
    replayed = runtime.register_request(
        settlement_request,
        channel_snapshot=snapshot(),
        now=NOW + timedelta(days=1),
    )
    assert replayed.reconciled_receipt == first


def test_restart_before_submission_preserves_authorization_and_zero_intents(
    tmp_path: Path,
) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    restarted = SettlementRuntime(runtime.path)
    assert restarted.get(settlement_request["settlement_id"]).state == "authorized"
    assert restarted.submit_intent_count(settlement_request["settlement_id"]) == 0
    technical = restarted.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW + timedelta(seconds=1),
    )
    assert technical.outcome == "accepted"
    assert restarted.submit_intent_count(settlement_request["settlement_id"]) == 1


def test_expired_authorization_fails_before_submit_intent(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    assert_error(
        "authorization_expired",
        runtime.submit,
        settlement_request["settlement_id"],
        executor=executor,
        now=datetime(2026, 8, 1, 0, 7, tzinfo=UTC),
    )
    assert runtime.submit_intent_count(settlement_request["settlement_id"]) == 0


def test_stale_snapshot_after_completed_settlement_rejects(tmp_path: Path) -> None:
    runtime, executor, _, channel, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature)
    runtime.reconcile(
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW + timedelta(seconds=1),
    )
    stale = request(channel, requested=1, suffix="stale")
    assert_error(
        "stale_snapshot",
        runtime.register_request,
        stale,
        channel_snapshot=channel,
        now=NOW,
    )


def test_observation_hash_tampering_rejects(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature)
    supplied["observation_hash"] = "sha256:" + ("0" * 64)
    assert_error(
        "observation_tampering",
        runtime.reconcile,
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW,
    )


def test_draft_schema_accepts_all_reference_runtime_objects(tmp_path: Path) -> None:
    schema = json.loads(
        (ROOT / "contracts" / "channel" / "settlement.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    runtime, executor, _, _, settlement_request, prepared = prepared_flow(tmp_path)
    commitment = runtime.commit_execution(
        settlement_request["settlement_id"],
        prepared,
        expected_signer=SIGNER,
        now=NOW,
    )
    technical = runtime.submit(
        settlement_request["settlement_id"],
        executor=executor,
        now=NOW,
    )
    supplied = observation(settlement_request, technical.transaction_signature)
    receipt = runtime.reconcile(
        settlement_request["settlement_id"],
        [supplied],
        observation_verifiers=observation_verifiers(supplied),
        now=NOW + timedelta(seconds=1),
    )
    assert receipt is not None
    values = [
        settlement_request,
        commitment.to_dict(),
        *[entry.to_dict() for entry in runtime.journal(settlement_request["settlement_id"])],
        technical.to_dict(),
        supplied,
        receipt.to_dict(),
    ]
    recovery_runtime, recovery_executor, _, _, recovery_request, _ = prepared_flow(
        tmp_path,
        suffix="recovery",
    )
    unknown = recovery_runtime.submit(
        recovery_request["settlement_id"],
        executor=recovery_executor,
        now=NOW,
        fault="after_commit_before_response",
    )
    recovery = recovery_runtime.recover(
        recovery_request["settlement_id"],
        executor=recovery_executor,
        now=NOW + timedelta(seconds=1),
    )
    values.extend([unknown.to_dict(), recovery.to_dict()])
    for value in values:
        assert list(validator.iter_errors(value)) == [], value


def test_journal_records_confirming_before_reconciling(tmp_path: Path) -> None:
    runtime, executor, _, _, settlement_request, _ = prepared_flow(tmp_path)
    runtime.submit(settlement_request["settlement_id"], executor=executor, now=NOW)
    states = [event.state for event in runtime.journal(settlement_request["settlement_id"])]
    assert states[-3:] == ["submitted", "confirming", "reconciling"]


def test_sqlite_connections_close_deterministically(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite3"
    runtime = SettlementRuntime(path)
    channel = snapshot()
    value = request(channel)
    runtime.register_request(value, channel_snapshot=channel, now=NOW)
    runtime.get(value["settlement_id"])
    runtime.journal(value["settlement_id"])
    path.unlink()
    assert not path.exists()


def test_runtime_source_has_no_rpc_wallet_solana_sdk_or_exactly_once_claim() -> None:
    source = (
        ROOT
        / "packages"
        / "channel-protocol"
        / "python"
        / "foundry_channel_protocol"
        / "settlement.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any(name == "solana" or name.startswith(("solana.", "solders")) for name in imported)
    lowered = source.lower()
    assert "exactly-once" not in lowered
    assert "exactly once" not in lowered
