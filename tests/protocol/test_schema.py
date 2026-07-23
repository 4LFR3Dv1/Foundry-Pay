from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from foundry_external_execution_protocol import economic_plan_hash


ROOT = Path(__file__).parents[2]
SCHEMA = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "schemas"
    / "external-execution-agent.v1.schema.json"
)
VECTOR = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "conformance"
    / "vectors"
    / "protocol-v1.json"
)


def request_fixture() -> dict:
    vector = json.loads(VECTOR.read_text(encoding="utf-8"))
    plan = vector["economic_plan"]
    return {
        "type": "external_execution_request",
        "protocol_version": "1.0.0",
        "execution_request_id": "exec_demo_001",
        "idempotency_key": "idem_demo_001",
        "economic_plan": plan,
        "economic_plan_hash": economic_plan_hash(plan),
        "economic_approval": {
            "approval_id": "approval_demo_001",
            "economic_plan_hash": economic_plan_hash(plan),
            "approved_by": "operator_demo",
            "issued_at": "2026-07-23T17:00:00Z",
            "expires_at": "2026-07-23T18:00:00Z",
        },
    }


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_external_execution_request_matches_protocol_schema() -> None:
    errors = list(validator().iter_errors(request_fixture()))
    assert errors == []


def test_schema_rejects_unknown_signed_property() -> None:
    request = copy.deepcopy(request_fixture())
    request["economic_plan"]["amount"] = 1.0
    errors = list(validator().iter_errors(request))
    assert errors
