"""Backfill the first live proof into the normative L1 observation format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .protocol import (
    SourceDescriptor,
    endpoint_identity_hash,
    normalize_observation,
    raw_response_hash,
)


def _raw_json_bytes(value: Any) -> bytes:
    """Serialize observed RPC data without applying domain-object null rules."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def backfill_fp_e2e_001(
    proof_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], SourceDescriptor]:
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    preparation = proof["executor_evidence"]["result"]["preparation_evidence"]
    status = proof["independent_chain_status"]
    before = proof["balances_before"]
    after = proof["balances_after"]
    descriptor = SourceDescriptor(
        source_id="foundry_l1_canonical_devnet",
        source_class="L1",
        source_kind="rpc",
        provider_id="solana_public_rpc",
        trust_domain_id="solana_public_infrastructure",
        endpoint_identity_hash=endpoint_identity_hash(preparation["rpc_endpoint"]),
        parser_id="fp_e2e_bundle_backfill_v1",
    )
    raw_slice = _raw_json_bytes(
        {
            "independent_chain_status": status,
            "balances_before": before,
            "balances_after": after,
        }
    )
    transaction_error = (
        "none" if status["err"] is None else raw_response_hash(_raw_json_bytes(status["err"]))
    )
    observation = normalize_observation(
        {
            "type": "source_observation",
            "protocol_version": "1.0.0",
            "normalization_profile": "foundry-pay-domain-v1",
            **descriptor.__dict__,
            "queried_at": proof["generated_at"],
            "signature": proof["signer_receipt"]["signature_envelope"],
            "network": proof["network"],
            "slot": status["slot"],
            "confirmation_status": status["confirmationStatus"],
            "transaction_error": transaction_error,
            "source_account": preparation["source_token_account"],
            "destination_account": preparation["destination_token_account"],
            "source_account_before": before["source_base_units"],
            "source_account_after": after["source_base_units"],
            "destination_account_before": before["destination_base_units"],
            "destination_account_after": after["destination_base_units"],
            "observed_amount_base_units": proof["economic_plan"]["amount_base_units"],
            "raw_response_hash": raw_response_hash(raw_slice),
        }
    )
    expected = {
        "execution_request_id": proof["prepared_execution"]["execution_request_id"],
        "obligation_id": proof["economic_plan"]["obligation_id"],
        "network": proof["network"],
        "signature": proof["signer_receipt"]["signature_envelope"],
        "source_account": preparation["source_token_account"],
        "destination_account": preparation["destination_token_account"],
        "amount_base_units": proof["economic_plan"]["amount_base_units"],
    }
    return expected, observation, descriptor


def write_fp_rec_001_evidence(
    proof_path: Path,
    output_directory: Path,
    *,
    implementation_commit: str,
) -> None:
    """Generate the reproducible L1 backfill and aggregate pending L2."""

    from .protocol import SourceRegistry, aggregate_reconciliation, observation_hash

    expected, observation, descriptor = backfill_fp_e2e_001(proof_path)
    result = aggregate_reconciliation(
        expected,
        [observation],
        SourceRegistry([descriptor]),
        unavailable_source_ids=["l2_provider_required"],
    )
    manifest = {
        "work_item": "FP-REC-001",
        "implementation_commit": implementation_commit,
        "live_l1": "verified",
        "live_l2": "pending_external_provider",
        "observation_hash": observation_hash(observation),
        "artifacts": [
            "l1-observation.json",
            "reconciliation-result.json",
        ],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "l1-observation.json": observation,
        "reconciliation-result.json": result,
        "manifest.json": manifest,
    }
    for name, payload in artifacts.items():
        (output_directory / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
