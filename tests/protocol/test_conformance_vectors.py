from __future__ import annotations

import json
from pathlib import Path

from foundry_external_execution_protocol import (
    economic_plan_hash,
    execution_commitment_hash,
    prepared_message_hash,
    simulation_attestation_hash,
)


VECTOR = (
    Path(__file__).parents[2]
    / "packages"
    / "external-execution-protocol"
    / "conformance"
    / "vectors"
    / "protocol-v1.json"
)


def test_protocol_v1_vector() -> None:
    vector = json.loads(VECTOR.read_text(encoding="utf-8"))

    assert economic_plan_hash(vector["economic_plan"]) == vector["economic_plan_hash"]
    assert (
        prepared_message_hash(bytes.fromhex(vector["prepared_message_hex"]))
        == vector["prepared_message_hash"]
    )
    assert (
        simulation_attestation_hash(vector["simulation_attestation"])
        == vector["simulation_attestation_hash"]
    )
    assert (
        execution_commitment_hash(vector["execution_commitment"])
        == vector["execution_commitment_hash"]
    )
