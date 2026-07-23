"""Regenerate the shared positive protocol vector from normative Python code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foundry_external_execution_protocol import (
    canonicalize,
    economic_plan_hash,
    execution_commitment_hash,
    normalize_economic_plan,
    prepared_message_hash,
    simulation_attestation_hash,
)

VECTOR_PATH = Path(__file__).parent / "vectors" / "protocol-v1.json"


def regenerate(vector: dict[str, Any]) -> dict[str, Any]:
    plan = normalize_economic_plan(vector["economic_plan"])
    message = bytes.fromhex(vector["prepared_message_hex"])
    simulation = vector["simulation_attestation"]
    current = vector["execution_commitment"]
    commitment = {
        "protocol_version": current["protocol_version"],
        "normalization_profile": current["normalization_profile"],
        "execution_request_id": current["execution_request_id"],
        "obligation_id": plan["obligation_id"],
        "executor_id": current["executor_id"],
        "executor_version": current["executor_version"],
        "economic_plan_hash": economic_plan_hash(plan),
        "prepared_message_hash": prepared_message_hash(message),
        "simulation_attestation_hash": simulation_attestation_hash(simulation),
        "signer": current["signer"],
        "constraints": current["constraints"],
        "expires_at": current["expires_at"],
    }
    return {
        **vector,
        "economic_plan": plan,
        "economic_plan_canonical_hex": canonicalize(plan).hex(),
        "economic_plan_hash": economic_plan_hash(plan),
        "prepared_message_hash": prepared_message_hash(message),
        "simulation_attestation_hash": simulation_attestation_hash(simulation),
        "execution_commitment": commitment,
        "execution_commitment_canonical_hex": canonicalize(commitment).hex(),
        "execution_commitment_hash": execution_commitment_hash(commitment),
    }


def main() -> None:
    vector = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    regenerated = regenerate(vector)
    VECTOR_PATH.write_text(
        json.dumps(regenerated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
