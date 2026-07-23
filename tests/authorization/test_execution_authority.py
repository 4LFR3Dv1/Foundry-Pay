from __future__ import annotations

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
import services.authorization.authority as authority_module
from jsonschema import Draft202012Validator

from foundry_external_execution_protocol import (
    economic_plan_hash,
    execution_commitment_hash,
    prepared_message_hash,
    simulation_attestation_hash,
)
from services.authorization import (
    AuthorizationConflict,
    AuthorizationExpired,
    AuthorizationInvalid,
    AuthorizationJournal,
    AuthorizationReplay,
    ExecutionAuthorizationAuthority,
)


ROOT = Path(__file__).parents[2]
SCHEMA = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "schemas"
    / "external-execution-agent.v1.schema.json"
)
PROTOCOL_VALIDATOR = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
NOW = datetime(2026, 7, 23, 16, 35, 40, tzinfo=UTC)
SOURCE = "9zsJvRFTxAG5sBuXhjMDZkgWb9oqQbK8gDywo7mUMNKb"
DESTINATION = "6dz2u59pmn9JnSMQMeB16Mq2iMDzx3Jz1Xa2dTdbxAiE"
MINT = "2tUzxADKHWxwTpihHuuzwfoGhYBY7735s2QXEuUcNX3k"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SYSTEM_PROGRAM = "11111111111111111111111111111111"
EXECUTION_REQUEST_ID = "exec_sa_gw_002_live_20260723T163529Z"
OBLIGATION_ID = "obl_sa_gw_002_live_20260723T163529Z"
LIVE_COMMITMENT = "sha256:e5e6ec585f0e46a6a77a2c07c291d9bb1b0c02c9c375297abdf739b00421ee79"


class RecordingSignatureProvider:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []

    def sign(self, payload: bytes) -> str:
        self.payloads.append(payload)
        return f"test-sha256:{hashlib.sha256(payload).hexdigest()}"


def economic_plan() -> dict:
    return {
        "protocol_version": "1.0.0",
        "normalization_profile": "foundry-pay-domain-v1",
        "obligation_id": OBLIGATION_ID,
        "network": "solana:devnet",
        "capability": "solana.spl_transfer.v1",
        "asset": {"kind": "spl-token", "mint": MINT, "decimals": 6},
        "amount_base_units": "1000000",
        "source": SOURCE,
        "destination": DESTINATION,
        "expires_at": "2026-07-23T16:50:29Z",
    }


def prepared_execution() -> dict:
    return {
        "type": "prepared_execution",
        "protocol_version": "1.0.0",
        "execution_request_id": EXECUTION_REQUEST_ID,
        "executor_id": "solana-agent",
        "executor_version": "0.2.0",
        "economic_plan_hash": "sha256:d1cff2a760c7ca3b377e1f640abfea194b939d1a48385e0f0838d87aad5adfb3",
        "prepared_message_base64": (
            "gAEAAgWFsHxvfs2yH1RgxBZctl8ZoLw6rc/w4PB7W+ABcqvB+oiiLZz5mG6tGo13"
            "1deKoFkkfkd38gqicxLl4LqSDiCYyExpveVZgDcjVfE+aGOlkifHBQKk+EaiEiUs"
            "I1/ioQoG3fbh12Whk9nL4UbO63msHLSF7V9bN5E6jPWFfv8AqRwL94kPv2krCiZw"
            "+yCBgni0b1KnXx+6CxMGt7TMCRavDj65uLmczb+f0v2jdSKLpjeKo+e29Dep1aB4"
            "aRxUXPEBAwQBBAIACgxAQg8AAAAAAAYA"
        ),
        "prepared_message_hash": "sha256:85a6b98ca7c050ee9dcba7aa0750d876a8ef5fd084458e768200256a9950cba6",
        "simulation": {
            "rpc_provider_id": "solana-devnet-public",
            "genesis_hash": "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG",
            "slot": 478362693,
            "commitment_level": "confirmed",
            "recent_blockhash": "xcBavHnRL6QhMdExzY8DnPQuFLweJ6JqZiDyie3qeD6",
            "last_valid_block_height": 466197815,
            "simulated_at": "2026-07-23T16:35:32Z",
            "valid_until": "2026-07-23T16:36:32Z",
            "logs_hash": "sha256:becedab55edbd5cd907943abc79f44ee3eba8d14fd9df58d841a38d05035bb70",
            "pre_balances_hash": "sha256:5b359b383ba646a49c66626085c30e4cfbcef983a6e9bb1db700fa18f4794990",
            "post_balances_hash": "sha256:88ecbd7cc446c368e14f6953a99992360c1431331e67b37a95c13a6fcea5e543",
            "accounts_observed_hash": "sha256:39bc72ff74f3cbde5f44f2059784905ec19210775de893b42f4b6747061acd21",
            "programs_observed_hash": "sha256:e53138d33bc1a6896b1c369580f25abd4097a677372cfcbd49e1f69a22aea407",
            "units_consumed": 105,
            "fee_lamports": 5000,
            "success": True,
        },
        "simulation_attestation_hash": "sha256:8ea92ac3e6cf487989c3292d6b67059be5fc32b5b3e13086a6d648e082efb75f",
        "execution_commitment_hash": LIVE_COMMITMENT,
        "signer": SOURCE,
        "constraints": {
            "max_fee_lamports": 50000,
            "allowed_programs": [TOKEN_PROGRAM],
        },
        "expires_at": "2026-07-23T16:36:32Z",
    }


def commitment(prepared: dict, plan: dict, *, obligation_id: str | None = None) -> dict:
    return {
        "protocol_version": prepared["protocol_version"],
        "normalization_profile": "foundry-pay-domain-v1",
        "execution_request_id": prepared["execution_request_id"],
        "obligation_id": obligation_id or plan["obligation_id"],
        "executor_id": prepared["executor_id"],
        "executor_version": prepared["executor_version"],
        "economic_plan_hash": prepared["economic_plan_hash"],
        "prepared_message_hash": prepared["prepared_message_hash"],
        "simulation_attestation_hash": prepared["simulation_attestation_hash"],
        "signer": prepared["signer"],
        "constraints": prepared["constraints"],
        "expires_at": prepared["expires_at"],
    }


def recommit(prepared: dict, plan: dict, *, obligation_id: str | None = None) -> None:
    prepared["execution_commitment_hash"] = execution_commitment_hash(
        commitment(prepared, plan, obligation_id=obligation_id)
    )


@pytest.fixture
def provider() -> RecordingSignatureProvider:
    return RecordingSignatureProvider()


@pytest.fixture
def authority(
    tmp_path: Path,
    provider: RecordingSignatureProvider,
) -> ExecutionAuthorizationAuthority:
    return ExecutionAuthorizationAuthority(
        AuthorizationJournal(tmp_path / "authorization.sqlite3"),
        signature_provider=provider,
    )


def issue(
    authority: ExecutionAuthorizationAuthority,
    *,
    plan: dict | None = None,
    prepared: dict | None = None,
    authorization_id: str = "auth_live_001",
    now: datetime = NOW,
    ttl_seconds: int = 30,
) -> dict:
    return authority.issue(
        economic_plan=plan or economic_plan(),
        prepared_execution=prepared or prepared_execution(),
        authorization_id=authorization_id,
        expected_execution_request_id=EXECUTION_REQUEST_ID,
        expected_executor_id="solana-agent",
        expected_signer=SOURCE,
        expected_constraints={
            "max_fee_lamports": 50000,
            "allowed_programs": [TOKEN_PROGRAM],
        },
        now=now,
        ttl_seconds=ttl_seconds,
    )


def test_live_commitment_is_verified_and_authorized(
    authority: ExecutionAuthorizationAuthority,
    provider: RecordingSignatureProvider,
) -> None:
    plan = economic_plan()
    prepared = prepared_execution()

    assert economic_plan_hash(plan) == prepared["economic_plan_hash"]
    assert (
        prepared_message_hash(base64.b64decode(prepared["prepared_message_base64"], validate=True))
        == prepared["prepared_message_hash"]
    )
    assert (
        simulation_attestation_hash(prepared["simulation"])
        == prepared["simulation_attestation_hash"]
    )
    assert execution_commitment_hash(commitment(prepared, plan)) == LIVE_COMMITMENT

    authorization = issue(authority, plan=plan, prepared=prepared)

    assert authorization["execution_commitment_hash"] == LIVE_COMMITMENT
    assert authorization["prepared_message_hash"] == prepared["prepared_message_hash"]
    assert authorization["single_use"] is True
    assert authorization["issued_at"] == "2026-07-23T16:35:40Z"
    assert authorization["expires_at"] == "2026-07-23T16:36:10Z"
    assert len(provider.payloads) == 1
    assert list(PROTOCOL_VALIDATOR.iter_errors(authorization)) == []


def test_any_changed_message_byte_is_rejected(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    prepared = prepared_execution()
    message = bytearray(base64.b64decode(prepared["prepared_message_base64"], validate=True))
    message[-1] ^= 1
    prepared["prepared_message_base64"] = base64.b64encode(message).decode("ascii")

    with pytest.raises(AuthorizationInvalid, match="prepared_message_hash mismatch"):
        issue(authority, prepared=prepared)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("signer", SYSTEM_PROGRAM, "signer does not match"),
        ("max_fee_lamports", 50001, "constraints do not match"),
        ("allowed_programs", [SYSTEM_PROGRAM], "constraints do not match"),
    ],
)
def test_authoritative_signer_fee_and_program_cannot_be_broadened(
    authority: ExecutionAuthorizationAuthority,
    field: str,
    value: object,
    error: str,
) -> None:
    plan = economic_plan()
    prepared = prepared_execution()
    if field == "signer":
        prepared[field] = value
    else:
        prepared["constraints"][field] = value
    recommit(prepared, plan)

    with pytest.raises(AuthorizationInvalid, match=error):
        issue(authority, plan=plan, prepared=prepared)


def test_commitment_cannot_be_rebound_to_another_obligation(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    plan = economic_plan()
    prepared = prepared_execution()
    recommit(prepared, plan, obligation_id="obl_other_001")

    with pytest.raises(AuthorizationInvalid, match="execution_commitment_hash mismatch"):
        issue(authority, plan=plan, prepared=prepared)


def test_request_and_executor_must_match_foundry_authority(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    prepared = prepared_execution()
    prepared["execution_request_id"] = "exec_other_001"
    recommit(prepared, economic_plan())
    with pytest.raises(AuthorizationInvalid, match="execution_request_id does not match"):
        issue(authority, prepared=prepared)

    prepared = prepared_execution()
    prepared["executor_id"] = "other-executor"
    recommit(prepared, economic_plan())
    with pytest.raises(AuthorizationInvalid, match="executor_id does not match"):
        issue(authority, prepared=prepared)


def test_simulation_tampering_and_failure_are_rejected(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    tampered = prepared_execution()
    tampered["simulation"]["fee_lamports"] = 5001
    with pytest.raises(AuthorizationInvalid, match="simulation_attestation_hash mismatch"):
        issue(authority, prepared=tampered)

    failed = prepared_execution()
    failed["simulation"]["success"] = False
    failed["simulation_attestation_hash"] = simulation_attestation_hash(failed["simulation"])
    recommit(failed, economic_plan())
    with pytest.raises(AuthorizationInvalid, match="simulation did not succeed"):
        issue(authority, prepared=failed)


@pytest.mark.parametrize("expired_input", ["plan", "simulation", "prepared"])
def test_expired_authority_inputs_are_rejected(
    authority: ExecutionAuthorizationAuthority,
    expired_input: str,
) -> None:
    plan = economic_plan()
    prepared = prepared_execution()
    if expired_input == "plan":
        plan["expires_at"] = "2026-07-23T16:35:39Z"
    elif expired_input == "simulation":
        prepared["simulation"]["valid_until"] = "2026-07-23T16:35:39Z"
        prepared["simulation_attestation_hash"] = simulation_attestation_hash(
            prepared["simulation"]
        )
        recommit(prepared, plan)
    else:
        prepared["expires_at"] = "2026-07-23T16:35:39Z"
        recommit(prepared, plan)

    with pytest.raises(AuthorizationExpired):
        issue(authority, plan=plan, prepared=prepared)


def test_authorization_never_outlives_prepared_execution(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    authorization = issue(
        authority,
        now=datetime(2026, 7, 23, 16, 35, 50, tzinfo=UTC),
        ttl_seconds=60,
    )

    assert authorization["expires_at"] == prepared_execution()["expires_at"]


def test_identical_issue_is_idempotent_but_second_active_grant_conflicts(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    first = issue(authority)
    replay = issue(authority)
    assert replay == first

    with pytest.raises(AuthorizationConflict, match="already has an active"):
        issue(authority, authorization_id="auth_live_002")


def test_concurrent_issue_creates_only_one_active_authorization(tmp_path: Path) -> None:
    journal_path = tmp_path / "authorization.sqlite3"

    def attempt(authorization_id: str) -> tuple[str, str]:
        authority = ExecutionAuthorizationAuthority(
            AuthorizationJournal(journal_path),
            signature_provider=RecordingSignatureProvider(),
        )
        try:
            authorization = issue(authority, authorization_id=authorization_id)
            return ("issued", authorization["authorization_id"])
        except AuthorizationConflict:
            return ("conflict", authorization_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ("auth_concurrent_001", "auth_concurrent_002")))

    assert sorted(status for status, _ in results) == ["conflict", "issued"]
    issued_id = next(identifier for status, identifier in results if status == "issued")
    assert AuthorizationJournal(journal_path).state(issued_id, now=NOW) == "issued"


def test_consumption_and_replay_survive_process_restart(
    tmp_path: Path,
    provider: RecordingSignatureProvider,
) -> None:
    path = tmp_path / "authorization.sqlite3"
    first = ExecutionAuthorizationAuthority(
        AuthorizationJournal(path),
        signature_provider=provider,
    )
    authorization = issue(first)

    restarted_journal = AuthorizationJournal(path)
    assert restarted_journal.state(authorization["authorization_id"], now=NOW) == "issued"
    consumed = restarted_journal.consume(authorization["authorization_id"], now=NOW)
    assert consumed == authorization

    after_consume = AuthorizationJournal(path)
    assert after_consume.state(authorization["authorization_id"], now=NOW) == "consumed"
    with pytest.raises(AuthorizationReplay):
        after_consume.consume(authorization["authorization_id"], now=NOW)


def test_expired_authorization_cannot_be_consumed(
    authority: ExecutionAuthorizationAuthority,
) -> None:
    authorization = issue(authority, ttl_seconds=1)

    with pytest.raises(AuthorizationExpired):
        authority.journal.consume(
            authorization["authorization_id"],
            now=datetime(2026, 7, 23, 16, 35, 42, tzinfo=UTC),
        )
    assert (
        authority.journal.state(
            authorization["authorization_id"],
            now=datetime(2026, 7, 23, 16, 35, 42, tzinfo=UTC),
        )
        == "expired"
    )


def test_service_has_no_solana_key_or_broadcast_capability() -> None:
    source = Path(authority_module.__file__).read_text(encoding="utf-8").lower()

    for forbidden in (
        "private_key",
        "seed_phrase",
        "keypair",
        "sendtransaction",
        "send_transaction",
        "broadcast",
        "solders",
        "solana.rpc",
    ):
        assert forbidden not in source
