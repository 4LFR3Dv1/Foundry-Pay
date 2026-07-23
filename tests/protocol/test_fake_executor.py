from __future__ import annotations

import base64
import copy
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from foundry_external_execution_protocol import (
    AuthorizationInvalid,
    AuthorizationMismatch,
    AuthorizationReplay,
    FakeAuthorizationAuthority,
    FakeExternalExecutor,
    IdempotencyConflict,
    FakeExecutorError,
    ObligationAlreadyExecuted,
    ResponseLost,
    economic_plan_hash,
    prepared_message_hash,
)


ROOT = Path(__file__).parents[2]
VECTOR = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "conformance"
    / "vectors"
    / "protocol-v1.json"
)
SCHEMA = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "schemas"
    / "external-execution-agent.v1.schema.json"
)
PROTOCOL_VALIDATOR = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
NOW = datetime(2026, 7, 23, 17, 30, tzinfo=UTC)
AUTHORITY_KEY = b"foundry-test-authorization-key-v1"
SIGNER = "11111111111111111111111111111111"


def assert_protocol_value(value: dict) -> None:
    assert list(PROTOCOL_VALIDATOR.iter_errors(value)) == []


@pytest.fixture
def vector() -> dict:
    return json.loads(VECTOR.read_text(encoding="utf-8"))


@pytest.fixture
def authority() -> FakeAuthorizationAuthority:
    return FakeAuthorizationAuthority(AUTHORITY_KEY)


@pytest.fixture
def executor(
    tmp_path: Path,
    authority: FakeAuthorizationAuthority,
) -> FakeExternalExecutor:
    return FakeExternalExecutor(
        tmp_path / "fake-executor.sqlite3",
        authorization_authority=authority,
    )


def request(vector: dict, *, request_id: str = "exec_demo_001") -> dict:
    plan = copy.deepcopy(vector["economic_plan"])
    plan_hash = economic_plan_hash(plan)
    return {
        "type": "external_execution_request",
        "protocol_version": "1.0.0",
        "execution_request_id": request_id,
        "idempotency_key": f"idem_{request_id}",
        "economic_plan": plan,
        "economic_plan_hash": plan_hash,
        "economic_approval": {
            "approval_id": f"approval_{request_id}",
            "economic_plan_hash": plan_hash,
            "approved_by": "operator_demo",
            "issued_at": "2026-07-23T17:00:00Z",
            "expires_at": "2026-07-23T18:00:00Z",
        },
    }


def simulation() -> dict:
    return {
        "rpc_provider_id": "rpc-demo",
        "genesis_hash": "g" * 32,
        "slot": 123,
        "commitment_level": "confirmed",
        "recent_blockhash": "b" * 32,
        "last_valid_block_height": 456,
        "simulated_at": "2026-07-23T17:29:00Z",
        "valid_until": "2026-07-23T17:55:00Z",
        "logs_hash": "sha256:" + "a" * 64,
        "pre_balances_hash": "sha256:" + "b" * 64,
        "post_balances_hash": "sha256:" + "c" * 64,
        "units_consumed": 1200,
        "fee_lamports": 5000,
        "success": True,
    }


def prepare(executor: FakeExternalExecutor, vector: dict, **request_options: str) -> dict:
    return executor.prepare(
        request(vector, **request_options),
        simulation=simulation(),
        signer=SIGNER,
        constraints={
            "max_fee_lamports": 50_000,
            "allowed_programs": [SIGNER],
        },
        expires_at="2026-07-23T17:50:00Z",
        now=NOW,
    )


def authorization(
    authority: FakeAuthorizationAuthority,
    prepared: dict,
    *,
    authorization_id: str = "auth_demo_001",
    issued_at: str = "2026-07-23T17:31:00Z",
    expires_at: str = "2026-07-23T17:40:00Z",
    single_use: bool = True,
) -> dict:
    return authority.issue(
        prepared,
        authorization_id=authorization_id,
        issued_at=issued_at,
        expires_at=expires_at,
        single_use=single_use,
    )


def test_prepare_binds_exact_materialized_message(
    executor: FakeExternalExecutor,
    vector: dict,
) -> None:
    prepared = prepare(executor, vector)
    message = base64.b64decode(prepared["prepared_message_base64"])
    assert prepared["prepared_message_hash"] == prepared_message_hash(message)
    assert prepared["economic_plan_hash"] == vector["economic_plan_hash"]
    assert executor.status("exec_demo_001")["state"] == "prepared"
    assert_protocol_value(prepared)

    repeated = prepare(executor, vector)
    assert repeated == prepared


def test_valid_single_use_authorization_executes_once(
    executor: FakeExternalExecutor,
    authority: FakeAuthorizationAuthority,
    vector: dict,
) -> None:
    prepared = prepare(executor, vector)
    grant = authorization(authority, prepared)
    receipt = executor.authorize_and_execute(
        grant,
        now=datetime(2026, 7, 23, 17, 32, tzinfo=UTC),
    )

    assert receipt == executor.receipt("exec_demo_001")
    assert receipt["prepared_message_hash"] == prepared["prepared_message_hash"]
    assert receipt["execution_commitment_hash"] == prepared["execution_commitment_hash"]
    status = executor.status("exec_demo_001")
    assert status["state"] == "confirmed"
    assert_protocol_value(status)
    assert_protocol_value(receipt)
    assert executor.effect_count("obl_demo_001") == 1

    with pytest.raises(AuthorizationReplay):
        executor.authorize_and_execute(
            grant,
            now=datetime(2026, 7, 23, 17, 33, tzinfo=UTC),
        )
    assert executor.effect_count("obl_demo_001") == 1


@pytest.mark.parametrize(
    ("issued_at", "expires_at", "single_use"),
    [
        ("2026-07-23T17:00:00Z", "2026-07-23T17:29:59Z", True),
        ("2026-07-23T17:31:00Z", "2026-07-23T17:40:00Z", False),
        ("2026-07-23T17:31:00Z", "2026-07-23T17:51:00Z", True),
    ],
)
def test_invalid_authorization_fails_before_effect(
    executor: FakeExternalExecutor,
    authority: FakeAuthorizationAuthority,
    vector: dict,
    issued_at: str,
    expires_at: str,
    single_use: bool,
) -> None:
    prepared = prepare(executor, vector)
    grant = authorization(
        authority,
        prepared,
        issued_at=issued_at,
        expires_at=expires_at,
        single_use=single_use,
    )
    with pytest.raises(AuthorizationInvalid):
        executor.authorize_and_execute(grant, now=NOW)
    assert executor.effect_count("obl_demo_001") == 0


def test_tampering_and_validly_signed_mismatch_fail_before_effect(
    executor: FakeExternalExecutor,
    authority: FakeAuthorizationAuthority,
    vector: dict,
) -> None:
    prepared = prepare(executor, vector)
    tampered = authorization(authority, prepared)
    tampered["prepared_message_hash"] = "sha256:" + "0" * 64
    with pytest.raises(AuthorizationInvalid):
        executor.authorize_and_execute(tampered, now=NOW)

    altered_prepared = copy.deepcopy(prepared)
    altered_prepared["prepared_message_hash"] = "sha256:" + "1" * 64
    signed_mismatch = authorization(
        authority,
        altered_prepared,
        authorization_id="auth_demo_mismatch",
    )
    with pytest.raises(AuthorizationMismatch):
        executor.authorize_and_execute(
            signed_mismatch,
            now=datetime(2026, 7, 23, 17, 32, tzinfo=UTC),
        )
    assert executor.effect_count("obl_demo_001") == 0


def test_idempotency_conflict_rejects_changed_plan(
    executor: FakeExternalExecutor,
    vector: dict,
) -> None:
    prepare(executor, vector)
    changed_request = request(vector)
    changed_request["economic_plan"]["amount_base_units"] = "1000001"
    changed_request["economic_plan_hash"] = economic_plan_hash(changed_request["economic_plan"])
    changed_request["economic_approval"]["economic_plan_hash"] = changed_request[
        "economic_plan_hash"
    ]

    with pytest.raises(IdempotencyConflict):
        executor.prepare(
            changed_request,
            simulation=simulation(),
            signer=SIGNER,
            constraints={
                "max_fee_lamports": 50_000,
                "allowed_programs": [SIGNER],
            },
            expires_at="2026-07-23T17:50:00Z",
            now=NOW,
        )
    assert executor.effect_count("obl_demo_001") == 0


def test_persisted_message_tampering_fails_before_effect(
    executor: FakeExternalExecutor,
    authority: FakeAuthorizationAuthority,
    vector: dict,
) -> None:
    prepared = prepare(executor, vector)
    grant = authorization(authority, prepared)
    tampered = copy.deepcopy(prepared)
    tampered["prepared_message_base64"] = base64.b64encode(b"different-message").decode("ascii")
    with sqlite3.connect(executor.database) as connection:
        connection.execute(
            """
            UPDATE executions
            SET prepared_json = ?
            WHERE execution_request_id = ?
            """,
            (
                json.dumps(tampered, separators=(",", ":"), sort_keys=True),
                prepared["execution_request_id"],
            ),
        )

    with pytest.raises(AuthorizationMismatch, match="message hash mismatch"):
        executor.authorize_and_execute(
            grant,
            now=datetime(2026, 7, 23, 17, 32, tzinfo=UTC),
        )
    assert executor.effect_count("obl_demo_001") == 0


def test_lost_response_recovers_durably_without_duplicate_effect(
    executor: FakeExternalExecutor,
    authority: FakeAuthorizationAuthority,
    vector: dict,
) -> None:
    prepared = prepare(executor, vector)
    grant = authorization(authority, prepared)

    with pytest.raises(ResponseLost):
        executor.authorize_and_execute(
            grant,
            now=datetime(2026, 7, 23, 17, 32, tzinfo=UTC),
            fault="after_commit_before_response",
        )

    restarted = FakeExternalExecutor(
        executor.database,
        authorization_authority=authority,
    )
    assert restarted.status("exec_demo_001")["state"] == "confirmed"
    recovered = restarted.recover(
        "exec_demo_001",
        observed_at=datetime(2026, 7, 23, 17, 34, tzinfo=UTC),
    )
    assert recovered["outcome"] == "confirmed"
    assert recovered["may_rematerialize"] is False
    recovered_receipt = restarted.receipt("exec_demo_001")
    assert recovered_receipt is not None
    assert_protocol_value(recovered)
    assert_protocol_value(recovered_receipt)
    assert restarted.effect_count("obl_demo_001") == 1

    with pytest.raises(AuthorizationReplay):
        restarted.authorize_and_execute(
            grant,
            now=datetime(2026, 7, 23, 17, 35, tzinfo=UTC),
        )
    assert restarted.effect_count("obl_demo_001") == 1

    with pytest.raises(ObligationAlreadyExecuted):
        prepare(restarted, vector, request_id="exec_demo_002")
    assert restarted.effect_count("obl_demo_001") == 1


def test_recovery_rejects_tampered_receipt(
    executor: FakeExternalExecutor,
    authority: FakeAuthorizationAuthority,
    vector: dict,
) -> None:
    prepared = prepare(executor, vector)
    grant = authorization(authority, prepared)
    with pytest.raises(ResponseLost):
        executor.authorize_and_execute(
            grant,
            now=datetime(2026, 7, 23, 17, 32, tzinfo=UTC),
            fault="after_commit_before_response",
        )
    receipt = executor.receipt("exec_demo_001")
    assert receipt is not None
    receipt["slot"] = 2
    with sqlite3.connect(executor.database) as connection:
        connection.execute(
            """
            UPDATE executions
            SET receipt_json = ?
            WHERE execution_request_id = ?
            """,
            (
                json.dumps(receipt, separators=(",", ":"), sort_keys=True),
                "exec_demo_001",
            ),
        )

    with pytest.raises(FakeExecutorError, match="receipt integrity"):
        executor.recover(
            "exec_demo_001",
            observed_at=datetime(2026, 7, 23, 17, 34, tzinfo=UTC),
        )
    assert executor.effect_count("obl_demo_001") == 1
