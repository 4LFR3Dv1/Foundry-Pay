"""SA-CHAN-000 adversarial fake-adapter conformance tests."""

from __future__ import annotations

import copy
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(ROOT / "packages" / "channel-protocol" / "python"))
sys.path.insert(0, str(ROOT / "services" / "fake-executor"))

from channel_adapter import FakeAdapterError, FakeChannelAdapter  # noqa: E402
from foundry_channel_protocol.capabilities import (  # noqa: E402
    CAPABILITY_ID,
    PROTOCOL_VERSION,
    CapabilityContractError,
    capability_manifest,
    prepare_operation,
)


NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
HASH_A = "sha256:" + ("a" * 64)


def request(*, suffix: str = "001") -> dict:
    return {
        "type": "channel_operation_request",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": f"request_{suffix}",
        "operation_id": f"operation_{suffix}",
        "idempotency_key": f"idempotency_{suffix}",
        "operation_kind": "settle",
        "channel_id": "channel_fixture_001",
        "epoch": 0,
        "sender": "sender_fixture",
        "recipient": "recipient_fixture",
        "destination_wallet": "wallet_fixture",
        "mint": "mint_fixture",
        "amount_base_units": "25000000",
        "authorization_commitment": HASH_A,
        "expires_at": "2026-08-10T12:10:00Z",
    }


def authorization(prepared: dict, *, suffix: str = "001") -> dict:
    return {
        "type": "channel_operation_authorization",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": prepared["request_id"],
        "operation_id": prepared["operation_id"],
        "prepared_material_hash": prepared["prepared_material_hash"],
        "operation_commitment": prepared["operation_commitment"],
        "authorization_id": f"authorization_{suffix}",
        "expires_at": "2026-08-10T12:05:00Z",
    }


def observation(receipt: dict, outcome: str = "matched") -> dict:
    return {
        "type": "channel_economic_observation",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": receipt["request_id"],
        "operation_id": receipt["operation_id"],
        "technical_receipt_hash": receipt["technical_receipt_hash"],
        "provider_ids": ["independent_fixture_a"],
        "economic_outcome": outcome,
        "observed_at": "2026-08-10T12:02:00Z",
    }


def recovery_request(prepared: dict) -> dict:
    return {
        "type": "channel_recovery_request",
        "protocol_version": PROTOCOL_VERSION,
        "capability_id": CAPABILITY_ID,
        "request_id": prepared["request_id"],
        "operation_id": prepared["operation_id"],
        "recovery_id": "recovery_001",
        "requested_at": "2026-08-10T12:01:00Z",
    }


def prepared_adapter(
    tmp_path: Path,
    *,
    scenario: str = "accepted",
    suffix: str = "001",
) -> tuple[FakeChannelAdapter, dict]:
    adapter = FakeChannelAdapter(tmp_path / "adapter.sqlite3")
    prepared = adapter.prepare(request(suffix=suffix), now=NOW)
    adapter.authorize(
        prepared["request_id"],
        authorization(prepared, suffix=suffix),
        now=NOW,
        scenario=scenario,
    )
    return adapter, prepared


def assert_adapter_error(code: str, function, *args, **kwargs) -> FakeAdapterError:
    with pytest.raises(FakeAdapterError) as captured:
        function(*args, **kwargs)
    assert captured.value.code == code
    return captured.value


def test_manifest_is_closed_fixture_only_and_schema_valid() -> None:
    value = capability_manifest()
    expected = json.loads(
        (ROOT / "contracts/channel/capabilities/capability-manifest.v0.json").read_text()
    )
    schema = json.loads(
        (
            ROOT / "contracts/channel/capabilities/channel-capability-manifest.v0.schema.json"
        ).read_text()
    )
    Draft202012Validator(schema).validate(value)
    assert value == expected
    descriptor = value["capabilities"][0]
    assert descriptor["authority"] == "none"
    assert descriptor["economic_completion"] is False
    assert descriptor["solana_compatibility"] == "not_claimed"


def test_request_and_prepared_contract_schemas_are_closed(tmp_path: Path) -> None:
    schema = json.loads(
        (ROOT / "contracts/channel/capabilities/channel-operation.v0.schema.json").read_text()
    )
    adapter = FakeChannelAdapter(tmp_path / "adapter.sqlite3")
    value = request()
    prepared = adapter.prepare(value, now=NOW)
    Draft202012Validator(schema).validate(value)
    Draft202012Validator(schema).validate(prepared)
    changed = {**value, "unknown": True}
    with pytest.raises(CapabilityContractError) as captured:
        prepare_operation(changed, now=NOW)
    assert captured.value.code == "closed_object_violation"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("protocol_version", "0.2.0", "unsupported_version"),
        ("capability_id", "foundry.channels.fixture.unknown.v0", "unsupported_capability"),
    ],
)
def test_unknown_version_and_capability_fail_closed(
    field: str,
    value: str,
    code: str,
) -> None:
    changed = request()
    changed[field] = value
    with pytest.raises(CapabilityContractError) as captured:
        prepare_operation(changed, now=NOW)
    assert captured.value.code == code


def test_preparation_is_deterministic_and_does_not_choose_economic_fields(tmp_path: Path) -> None:
    adapter = FakeChannelAdapter(tmp_path / "adapter.sqlite3")
    value = request()
    first = adapter.prepare(value, now=NOW)
    repeated = adapter.prepare(value, now=NOW)
    assert repeated == first
    assert first["prepared_material_hash"].startswith("sha256:")
    status = adapter.status(value["request_id"])
    assert status.state == "prepared"
    assert status.submit_intent_count == 0
    assert status.technical_receipt is None


def test_same_request_id_with_different_bytes_is_idempotency_conflict(tmp_path: Path) -> None:
    adapter = FakeChannelAdapter(tmp_path / "adapter.sqlite3")
    value = request()
    adapter.prepare(value, now=NOW)
    changed = copy.deepcopy(value)
    changed["amount_base_units"] = "25000001"
    assert_adapter_error("idempotency_conflict", adapter.prepare, changed, now=NOW)


def test_authorization_rejection_and_exact_byte_tampering_are_observable(
    tmp_path: Path,
) -> None:
    adapter = FakeChannelAdapter(tmp_path / "adapter.sqlite3")
    prepared = adapter.prepare(request(), now=NOW)
    assert_adapter_error(
        "authorization_rejected",
        adapter.authorize,
        prepared["request_id"],
        authorization(prepared),
        now=NOW,
        scenario="authorization_rejected",
    )
    assert adapter.status(prepared["request_id"]).state == "prepared"

    changed = authorization(prepared)
    changed["prepared_material_hash"] = "sha256:" + ("b" * 64)
    assert_adapter_error(
        "authorization_mismatch",
        adapter.authorize,
        prepared["request_id"],
        changed,
        now=NOW,
        scenario="accepted",
    )
    assert adapter.status(prepared["request_id"]).state == "prepared"


def test_definitive_pre_submission_failure_has_no_submit_intent(tmp_path: Path) -> None:
    adapter, prepared = prepared_adapter(
        tmp_path,
        scenario="definitive_pre_submission_failure",
    )
    status = adapter.submit(prepared["request_id"], now=NOW)
    assert status.state == "failed_definitive"
    assert status.submit_intent_count == 0
    assert status.automatic_resubmission_count == 0


def test_authorized_and_submitted_are_distinct_durable_states(tmp_path: Path) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="submitted")
    authorized = adapter.status(prepared["request_id"])
    assert authorized.state == "authorized"
    submitted = adapter.submit(prepared["request_id"], now=NOW)
    assert submitted.state == "submitted"
    assert submitted.submit_intent_count == 1
    assert submitted.technical_receipt is None
    assert submitted.reconciled_result is None


def test_technical_confirmation_is_not_reconciliation(tmp_path: Path) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="accepted")
    status = adapter.submit(prepared["request_id"], now=NOW)
    assert status.state == "confirmed"
    assert status.technical_receipt is not None
    assert status.reconciled_result is None
    status_schema = json.loads(
        (ROOT / "contracts/channel/capabilities/channel-status-recovery.v0.schema.json").read_text()
    )
    receipt_schema = json.loads(
        (
            ROOT / "contracts/channel/capabilities/channel-receipt-reconciliation.v0.schema.json"
        ).read_text()
    )
    Draft202012Validator(status_schema).validate(status.as_contract())
    Draft202012Validator(receipt_schema).validate(status.technical_receipt)


@pytest.mark.parametrize(
    ("outcome", "expected_state"),
    [("matched", "reconciled"), ("mismatch", "needs_review"), ("divergent", "disputed")],
)
def test_reconciliation_outcomes_are_not_collapsed(
    tmp_path: Path,
    outcome: str,
    expected_state: str,
) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="accepted")
    confirmed = adapter.submit(prepared["request_id"], now=NOW)
    result = adapter.reconcile(
        prepared["request_id"],
        observation(confirmed.technical_receipt, outcome),
        now=NOW,
    )
    assert result.state == expected_state
    assert (result.reconciled_result is not None) is (outcome == "matched")


def test_receipt_incompatible_with_request_rejects(tmp_path: Path) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="accepted")
    confirmed = adapter.submit(prepared["request_id"], now=NOW)
    changed = observation(confirmed.technical_receipt)
    changed["operation_id"] = "operation_other"
    assert_adapter_error(
        "observation_mismatch",
        adapter.reconcile,
        prepared["request_id"],
        changed,
        now=NOW,
    )
    assert adapter.status(prepared["request_id"]).state == "confirmed"


@pytest.mark.parametrize("provider_id", ["provider with spaces", "p" * 129])
def test_provider_identifiers_match_the_closed_schema(
    tmp_path: Path,
    provider_id: str,
) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="accepted")
    confirmed = adapter.submit(prepared["request_id"], now=NOW)
    changed = observation(confirmed.technical_receipt)
    changed["provider_ids"] = [provider_id]
    assert_adapter_error(
        "invalid_providers",
        adapter.reconcile,
        prepared["request_id"],
        changed,
        now=NOW,
    )
    assert adapter.status(prepared["request_id"]).state == "confirmed"


def test_lost_response_restart_recovery_never_submits_twice(tmp_path: Path) -> None:
    database = tmp_path / "adapter.sqlite3"
    adapter = FakeChannelAdapter(database)
    prepared = adapter.prepare(request(), now=NOW)
    adapter.authorize(
        prepared["request_id"],
        authorization(prepared),
        now=NOW,
        scenario="lost_response",
    )
    status = adapter.submit(prepared["request_id"], now=NOW)
    assert status.state == "needs_recovery"
    assert status.submit_intent_count == 1
    assert_adapter_error(
        "recovery_required",
        adapter.submit,
        prepared["request_id"],
        now=NOW,
    )

    restarted = FakeChannelAdapter(database)
    recovery = recovery_request(prepared)
    recovery_schema = json.loads(
        (ROOT / "contracts/channel/capabilities/channel-status-recovery.v0.schema.json").read_text()
    )
    Draft202012Validator(recovery_schema).validate(recovery)
    recovered = restarted.recover_from_contract(recovery, now=NOW)
    Draft202012Validator(recovery_schema).validate(recovered)
    assert recovered["outcome"] == "confirmed"
    assert recovered["new_submission_attempted"] is False
    assert recovered["may_rematerialize"] is False
    final = restarted.status(prepared["request_id"])
    assert final.submit_intent_count == 1
    assert final.automatic_resubmission_count == 0


def test_inconclusive_recovery_is_repeatable_and_remains_needs_recovery(
    tmp_path: Path,
) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="recovery_inconclusive")
    adapter.submit(prepared["request_id"], now=NOW)
    first = adapter.recover(prepared["request_id"], now=NOW)
    second = FakeChannelAdapter(tmp_path / "adapter.sqlite3").recover(
        prepared["request_id"],
        now=NOW,
    )
    assert first["outcome"] == second["outcome"] == "unknown"
    status = adapter.status(prepared["request_id"])
    assert status.state == "needs_recovery"
    assert status.submit_intent_count == 1
    assert status.automatic_resubmission_count == 0


def test_authorization_replay_fails_closed(tmp_path: Path) -> None:
    adapter = FakeChannelAdapter(tmp_path / "adapter.sqlite3")
    first = adapter.prepare(request(), now=NOW)
    auth = authorization(first)
    adapter.authorize(first["request_id"], auth, now=NOW, scenario="accepted")
    second_request = request(suffix="002")
    second = adapter.prepare(second_request, now=NOW)
    replay = {
        **auth,
        "request_id": second["request_id"],
        "operation_id": second["operation_id"],
        "prepared_material_hash": second["prepared_material_hash"],
        "operation_commitment": second["operation_commitment"],
    }
    assert_adapter_error(
        "authorization_replay",
        adapter.authorize,
        second["request_id"],
        replay,
        now=NOW,
        scenario="accepted",
    )
    assert adapter.status(second["request_id"]).state == "prepared"


def test_two_concurrent_submissions_create_one_controlled_attempt(tmp_path: Path) -> None:
    adapter, prepared = prepared_adapter(tmp_path, scenario="accepted")

    def submit() -> str:
        try:
            return (
                FakeChannelAdapter(tmp_path / "adapter.sqlite3")
                .submit(
                    prepared["request_id"],
                    now=NOW,
                )
                .state
            )
        except FakeAdapterError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(lambda _: submit(), range(2)))
    assert results == ["confirmed", "invalid_state"]
    status = adapter.status(prepared["request_id"])
    assert status.submit_intent_count == 1
    assert status.automatic_resubmission_count == 0


def test_no_module_imports_solana_wallet_signer_rpc_or_idl() -> None:
    source = (
        (ROOT / "services/fake-executor/channel_adapter.py").read_text(encoding="utf-8").lower()
    )
    forbidden_imports = (
        "import solana",
        "from solana",
        "anchorpy",
        "wallet_adapter",
        "keypair",
        "private_key",
    )
    assert not any(value in source for value in forbidden_imports)
