from __future__ import annotations

import copy

import pytest

from foundry_external_execution_protocol import (
    DomainNormalizationError,
    economic_plan_hash,
    execution_commitment_hash,
    normalize_economic_plan,
    prepared_message_hash,
    simulation_attestation_hash,
)


PUBKEY_A = "11111111111111111111111111111111"
PUBKEY_B = "SysvarRent111111111111111111111111111111111"


@pytest.fixture
def economic_plan() -> dict:
    return {
        "protocol_version": "1.0.0",
        "normalization_profile": "foundry-pay-domain-v1",
        "obligation_id": "obl_demo_001",
        "network": "solana-devnet",
        "asset": {
            "kind": "spl-token",
            "mint": PUBKEY_A,
            "decimals": 6,
        },
        "amount_base_units": "1000000",
        "source": PUBKEY_A,
        "destination": PUBKEY_B,
        "reason": "synthetic reconciliation fixture",
        "expires_at": "2026-07-23T18:00:00Z",
    }


def test_economic_hash_is_order_independent(economic_plan: dict) -> None:
    reordered = {key: economic_plan[key] for key in reversed(economic_plan)}
    assert economic_plan_hash(reordered) == economic_plan_hash(economic_plan)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount_base_units", "01"),
        ("amount_base_units", 1_000_000),
        ("amount_base_units", "0"),
        ("network", "devnet"),
        ("expires_at", "2026-07-23T18:00:00+00:00"),
    ],
)
def test_rejects_noncanonical_domain_values(
    economic_plan: dict,
    field: str,
    value: object,
) -> None:
    economic_plan[field] = value
    with pytest.raises(DomainNormalizationError):
        normalize_economic_plan(economic_plan)


def test_rejects_unknown_and_null_fields(economic_plan: dict) -> None:
    economic_plan["memo"] = "not signed by v1"
    with pytest.raises(DomainNormalizationError, match="unknown keys"):
        normalize_economic_plan(economic_plan)

    economic_plan.pop("memo")
    economic_plan["reason"] = None
    with pytest.raises(DomainNormalizationError, match="null is forbidden"):
        normalize_economic_plan(economic_plan)


def test_prepared_message_hash_binds_exact_bytes() -> None:
    original = bytes.fromhex("01020304")
    changed = bytes.fromhex("01020305")
    assert prepared_message_hash(original) != prepared_message_hash(changed)


def test_execution_commitment_binds_plan_message_and_simulation(
    economic_plan: dict,
) -> None:
    simulation = {
        "rpc_provider_id": "rpc-demo",
        "slot": 123,
        "success": True,
        "logs_hash": "sha256:" + "a" * 64,
    }
    commitment = {
        "protocol_version": "1.0.0",
        "normalization_profile": "foundry-pay-domain-v1",
        "execution_request_id": "exec_demo_001",
        "executor_id": "solana-agent",
        "executor_version": "0.1.0",
        "economic_plan_hash": economic_plan_hash(economic_plan),
        "prepared_message_hash": prepared_message_hash(b"message-v1"),
        "simulation_attestation_hash": simulation_attestation_hash(simulation),
        "signer": PUBKEY_A,
        "constraints": {
            "max_fee_lamports": 50000,
            "allowed_programs": [PUBKEY_A],
        },
        "expires_at": "2026-07-23T18:00:00Z",
    }
    original = execution_commitment_hash(commitment)

    mutated = copy.deepcopy(commitment)
    mutated["prepared_message_hash"] = prepared_message_hash(b"message-v2")
    assert execution_commitment_hash(mutated) != original


def test_rejects_floats_in_signed_constraints(economic_plan: dict) -> None:
    commitment = {
        "protocol_version": "1.0.0",
        "normalization_profile": "foundry-pay-domain-v1",
        "execution_request_id": "exec_demo_001",
        "executor_id": "solana-agent",
        "executor_version": "0.1.0",
        "economic_plan_hash": economic_plan_hash(economic_plan),
        "prepared_message_hash": prepared_message_hash(b"message-v1"),
        "simulation_attestation_hash": "sha256:" + "a" * 64,
        "signer": PUBKEY_A,
        "constraints": {"max_fee_sol": 0.000005},
        "expires_at": "2026-07-23T18:00:00Z",
    }
    with pytest.raises(DomainNormalizationError, match="floating-point"):
        execution_commitment_hash(commitment)
