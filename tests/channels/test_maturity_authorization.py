from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "contracts/governance/examples/fc-proto-007-self-validated.json"
CURRENT_COMMIT = "37eda9929f87f9c60c29f0483aaf59739aab7f0a"
OTHER_COMMIT = "0" * 40


def load_checker() -> ModuleType:
    path = ROOT / "scripts/check_maturity_authorization.py"
    spec = importlib.util.spec_from_file_location("check_maturity_authorization", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def example() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_self_validated_offline_record_is_valid_and_explicitly_unaudited() -> None:
    record = example()
    assert load_checker().validate_record(record) == []
    assert record["maturity"]["external_review"]["status"] == "not_performed"
    assert record["deployment_authorization"]["mainnet"]["status"] == "blocked"
    assert record["deployment_authorization"]["real_value"]["status"] == "blocked"


def test_schema_is_closed_and_requires_block_reason() -> None:
    checker = load_checker()
    record = example()
    record["unexpected"] = True
    assert any("Additional properties" in error for error in checker.validate_record(record))

    record = example()
    record["deployment_authorization"]["mainnet"]["reason"] = None
    assert checker.validate_record(record)


def test_passed_validation_and_review_must_bind_current_commit() -> None:
    checker = load_checker()
    record = example()
    record["maturity"]["self_validation"]["validated_commit"] = OTHER_COMMIT
    assert checker.validate_record(record) == [
        "passed self-validation must bind current_commit; use stale otherwise"
    ]

    record = reviewed_record()
    record["maturity"]["external_review"]["reviewed_commit"] = OTHER_COMMIT
    assert checker.validate_record(record) == [
        "passed external review must bind current_commit; use stale otherwise"
    ]


def test_stale_review_preserves_historical_evidence_without_authorizing_current() -> None:
    checker = load_checker()
    record = reviewed_record()
    record["maturity"]["external_review"]["status"] = "stale"
    record["maturity"]["external_review"]["reviewed_commit"] = OTHER_COMMIT
    assert checker.validate_record(record) == []

    record["deployment_authorization"]["mainnet"] = allowed_authorization()
    assert "mainnet requires passed exact-version external review" in checker.validate_record(
        record
    )


def test_stale_review_requires_preserved_historical_evidence() -> None:
    checker = load_checker()
    record = example()
    record["maturity"]["external_review"]["status"] = "stale"
    assert checker.validate_record(record)


def test_experimental_authorization_requires_current_self_validation() -> None:
    checker = load_checker()
    record = example()
    record["maturity"]["self_validation"] = {
        "status": "not_performed",
        "validated_commit": None,
        "evidence": None,
    }
    assert checker.validate_record(record) == [
        "local_validator requires passed exact-version self-validation"
    ]


def test_mainnet_and_real_value_require_review_and_closed_constraints() -> None:
    checker = load_checker()
    record = example()
    record["deployment_authorization"]["mainnet"] = allowed_authorization()
    errors = checker.validate_record(record)
    assert "mainnet requires passed exact-version external review" in errors
    assert any(error.startswith("mainnet missing constraints:") for error in errors)

    record = reviewed_record()
    authorization = allowed_authorization()
    authorization["constraints"] = {
        "cluster": "mainnet-beta",
        "program_id": "11111111111111111111111111111111",
        "idl_sha256": "sha256:" + "1" * 64,
        "mint": "So11111111111111111111111111111111111111112",
        "upgrade_authority": "11111111111111111111111111111111",
        "max_value_base_units": "1000000",
    }
    record["deployment_authorization"]["mainnet"] = copy.deepcopy(authorization)
    record["deployment_authorization"]["real_value"] = copy.deepcopy(authorization)
    assert checker.validate_record(record) == []


def reviewed_record() -> dict[str, Any]:
    record = example()
    record["maturity"]["external_review"] = {
        "status": "passed",
        "reviewed_commit": CURRENT_COMMIT,
        "reviewer": "independent-reviewer",
        "report": "reviews/fc-proto-007.md",
        "completed_at": "2026-07-27T12:00:00Z",
    }
    return record


def allowed_authorization() -> dict[str, Any]:
    return {
        "status": "allowed",
        "scope": "exact artifact only",
        "artifact_commit": CURRENT_COMMIT,
        "decision_ref": "FC-ADR-009",
        "reason": None,
        "constraints": {},
    }
