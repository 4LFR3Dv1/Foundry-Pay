"""Contract tests for FC-SEC-002 signed-preimage mutation cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(ROOT / "packages/channel-protocol/python"))

from foundry_channel_protocol.conformance_runner import run_security_cases  # noqa: E402


CASES = Path(__file__).with_name("mutation-cases.json")
REGISTRY = ROOT / "contracts/channel/canonicalization"
EXPECTATIONS = (
    ROOT
    / "contracts/channel/test-vectors/negative"
    / "fc-sec-002/signed-preimage-mutations-v1.json"
)


def test_all_mutations_fail_closed_without_authority_effect() -> None:
    results = run_security_cases(CASES, REGISTRY)

    assert len(results) == 23
    assert {result["decision"] for result in results} == {"reject"}
    assert {result["economic_effect_count"] for result in results} == {0}
    assert {result["authority_advancement_count"] for result in results} == {0}
    assert {result["lifecycle_transition_count"] for result in results} == {0}
    assert {result["verified_transition_count"] for result in results} == {0}
    assert {result["activation_requested_transition_count"] for result in results} == {0}
    assert {result["authorized_transition_count"] for result in results} == {0}
    assert {result["completed_transition_count"] for result in results} == {0}


def test_mutations_cover_material_domains_and_fail_at_stable_stages() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    results = {result["case_id"]: result for result in run_security_cases(CASES, REGISTRY)}

    voucher_fields = {
        case["path"][-1]
        for case in cases
        if case["case_id"].startswith("voucher-") and case["case_id"] != "voucher-as-binding"
    }
    assert {
        "domain",
        "protocol_version",
        "environment",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "channel_account",
        "epoch",
        "sender",
        "recipient_claim_pubkey",
        "mint",
        "sequence",
        "previous_activated_voucher_hash",
        "cumulative_authorized_base_units",
        "expires_at",
    } <= voucher_fields

    assert results["voucher-domain"]["stage"] == "domain_verification"
    assert results["voucher-domain"]["code"] == "domain_mismatch"
    assert results["voucher-version"]["stage"] == "version_verification"
    assert results["voucher-version"]["code"] == "unsupported_version"
    assert results["unknown-profile"]["stage"] == "profile_verification"
    assert results["unknown-profile"]["code"] == "unsupported_profile"
    assert results["voucher-as-binding"]["code"] == "object_type_mismatch"
    assert results["binding-as-voucher"]["code"] == "object_type_mismatch"

    preimage_rejections = [
        result for result in results.values() if result["stage"] == "signed_preimage_verification"
    ]
    assert preimage_rejections
    for result in preimage_rejections:
        assert result["code"] == "signed_preimage_mismatch"
        assert result["mutated_byte_length"] > 0
        assert result["mutated_sha256"].startswith("sha256:")


def test_python_output_matches_published_expectations_exactly() -> None:
    expected = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    assert expected["runner_reads_expectations"] is False
    actual = run_security_cases(CASES, REGISTRY)

    for result, expectation in zip(actual, expected["expectations"], strict=True):
        assert {
            field: value
            for field, value in result.items()
            if field
            not in {
                "implementation",
                "runtime_version",
                "runner_contract",
                "runner_version",
                "schema_version",
            }
        } == expectation
