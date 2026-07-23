from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from foundry_external_execution_protocol import (
    DomainNormalizationError,
    canonicalize,
    economic_plan_hash,
    execution_commitment_hash,
    normalize_economic_plan,
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
NEGATIVE_VECTOR = (
    Path(__file__).parents[2]
    / "packages"
    / "external-execution-protocol"
    / "conformance"
    / "vectors"
    / "negative-v1.json"
)


def set_path(target: dict, path: list[str], value: object) -> None:
    cursor = target
    for segment in path[:-1]:
        cursor = cursor[segment]
    cursor[path[-1]] = value


def test_protocol_v1_vector() -> None:
    vector = json.loads(VECTOR.read_text(encoding="utf-8"))

    assert economic_plan_hash(vector["economic_plan"]) == vector["economic_plan_hash"]
    assert (
        canonicalize(normalize_economic_plan(vector["economic_plan"])).hex()
        == vector["economic_plan_canonical_hex"]
    )
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
    assert (
        canonicalize(vector["execution_commitment"]).hex()
        == vector["execution_commitment_canonical_hex"]
    )


def test_shared_negative_vectors_fail() -> None:
    vector = json.loads(VECTOR.read_text(encoding="utf-8"))
    negative_vector = json.loads(NEGATIVE_VECTOR.read_text(encoding="utf-8"))

    for negative in negative_vector["cases"]:
        target = copy.deepcopy(vector[negative["target"]])
        set_path(target, negative["path"], negative["value"])
        operation = (
            economic_plan_hash
            if negative["target"] == "economic_plan"
            else execution_commitment_hash
        )
        with pytest.raises(DomainNormalizationError, match=".+"):
            operation(target)
