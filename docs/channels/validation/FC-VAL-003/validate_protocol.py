"""Static verification for the public FC-VAL-003 protocol kit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent


def load_json(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def scores_a(value: int = 2) -> dict[str, int]:
    return {f"A{index}": value for index in range(1, 7)}


def scores_b(value: bool = True) -> dict[str, bool]:
    return {f"B{index}": value for index in range(1, 11)}


def valid_eligible() -> dict[str, Any]:
    return {
        "protocol_version": "fc-val-003-v1",
        "run_id": "FCVAL003-7KQ9M2WX",
        "record_id": "7KQ9M2WX4RTY",
        "record_status": "eligible_complete",
        "stage_reached": "completed",
        "segment": {"repeat_sender": True, "own_wallet_recipient": True},
        "stage_a": {
            "locked_before_stage_b": True,
            "locked_record_sha256": f"sha256:{'a' * 64}",
            "primary": scores_a(),
            "secondary": scores_a(),
            "adjudicated": scores_a(),
        },
        "stage_b": {
            "primary": scores_b(),
            "secondary": scores_b(),
            "adjudicated": scores_b(),
        },
        "misconceptions": [],
        "ratings": {"clarity_1_to_5": 4, "reuse_intent_1_to_5": 3},
        "scoring": {
            "status": "final_adjudicated",
            "second_review_completed": True,
            "disagreement_count": 0,
            "ambiguity_count": 0,
            "adjudication_count": 0,
            "private_audit_ref": "AUDIT-7KQ9M2WX4R",
        },
    }


def assert_valid(validator: Draft202012Validator, instance: dict[str, Any]) -> None:
    errors = list(validator.iter_errors(instance))
    assert not errors, errors


def assert_invalid(validator: Draft202012Validator, instance: dict[str, Any]) -> None:
    assert list(validator.iter_errors(instance)), instance


def main() -> None:
    result_schema = load_json("result-record.schema.json")
    manifest_schema = load_json("run-manifest.schema.json")
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator.check_schema(manifest_schema)
    validator = Draft202012Validator(result_schema)

    eligible = valid_eligible()
    assert_valid(validator, eligible)
    assert_valid(
        validator,
        {
            "protocol_version": "fc-val-003-v1",
            "run_id": "FCVAL003-7KQ9M2WX",
            "record_status": "ineligible",
            "stage_reached": "screening",
            "exclusion_reason": "PRIOR_PROTOCOL_EXPOSURE",
        },
    )
    assert_valid(
        validator,
        {
            "protocol_version": "fc-val-003-v1",
            "run_id": "FCVAL003-7KQ9M2WX",
            "record_id": "Q7M9WX4RTY2K",
            "record_status": "incomplete",
            "stage_reached": "stage_a",
            "attrition_reason": "PARTICIPANT_STOPPED",
        },
    )
    assert_valid(
        validator,
        {
            "protocol_version": "fc-val-003-v1",
            "run_id": "FCVAL003-7KQ9M2WX",
            "record_status": "withdrawn",
            "stage_reached": "stage_b",
            "withdrawal_disposition": "PARTICIPANT_DATA_DELETED_BEFORE_AGGREGATION",
        },
    )

    missing_segment = dict(eligible)
    missing_segment.pop("segment")
    assert_invalid(validator, missing_segment)
    sequential_id = dict(eligible)
    sequential_id["record_id"] = "P01"
    assert_invalid(validator, sequential_id)
    unlocked_stage_a = json.loads(json.dumps(eligible))
    unlocked_stage_a["stage_a"]["locked_before_stage_b"] = False
    assert_invalid(validator, unlocked_stage_a)
    no_second_review = json.loads(json.dumps(eligible))
    no_second_review["scoring"]["second_review_completed"] = False
    assert_invalid(validator, no_second_review)
    incomplete_with_scores = {
        "protocol_version": "fc-val-003-v1",
        "run_id": "FCVAL003-7KQ9M2WX",
        "record_id": "Q7M9WX4RTY2K",
        "record_status": "incomplete",
        "stage_reached": "stage_a",
        "attrition_reason": "PARTICIPANT_STOPPED",
        "stage_a": scores_a(0),
    }
    assert_invalid(validator, incomplete_with_scores)
    withdrawn_with_identifier = {
        "protocol_version": "fc-val-003-v1",
        "run_id": "FCVAL003-7KQ9M2WX",
        "record_id": "Q7M9WX4RTY2K",
        "record_status": "withdrawn",
        "stage_reached": "stage_b",
        "withdrawal_disposition": "PARTICIPANT_DATA_DELETED_BEFORE_AGGREGATION",
    }
    assert_invalid(validator, withdrawn_with_identifier)

    template = load_json("participant-record.template.json")
    assert "_template_only" in template
    assert list(validator.iter_errors(template))

    aggregate = load_json("sanitized-results.template.json")
    assert aggregate["run_status"] == "not_started"
    assert aggregate["privacy_review"]["status"] == "not_performed"
    assert aggregate["sample"]["eligible_completed_total"] == 0
    assert aggregate["small_cell_policy"]["participant_level_exports"] is False
    assert aggregate["small_cell_policy"]["cross_tabs"] is False
    assert aggregate["small_cell_policy"]["verbatim_quotes"] is False
    assert aggregate["stage_b_taught"]["cannot_override_stage_a"] is True

    manifest_template = load_json("RUN_MANIFEST.template.json")
    assert "_template_only" in manifest_template
    assert manifest_template["privacy_approvals"]["approved_before_recruitment"] is False
    assert list(Draft202012Validator(manifest_schema).iter_errors(manifest_template))

    required_privacy_terms = [
        "controller_name:",
        "processing_basis_review_id:",
        "storage_approval_id:",
        "withdrawal_cutoff:",
        "backup expiry/deletion",
        "recording consent separately",
    ]
    checklist = (ROOT / "PRE_RECRUITMENT_CHECKLIST.md").read_text(encoding="utf-8")
    for term in required_privacy_terms:
        assert term in checklist

    print(
        "schemas=2 valid_status_cases=4 rejected_unsafe_cases=6 "
        "privacy_template=blocked aggregate_template=empty"
    )


if __name__ == "__main__":
    main()
