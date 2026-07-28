from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[4]
GOVERNANCE = ROOT / "docs/channels/solana/governance"
MANIFEST = ROOT / "programs/foundry-channel-vault/governance-model/Cargo.toml"


def load(name: str) -> dict:
    return json.loads((GOVERNANCE / name).read_text(encoding="utf-8"))


def cargo() -> str:
    executable = shutil.which("cargo")
    if executable:
        return executable
    candidate = (
        Path.home() / ".cargo/bin" / ("cargo.exe" if __import__("os").name == "nt" else "cargo")
    )
    assert candidate.exists()
    return str(candidate)


def test_upgrade_manifest_schema_is_closed_and_accepts_complete_fixture() -> None:
    schema = load("upgrade-manifest-schema.json")
    Draft202012Validator.check_schema(schema)
    fixture = {
        "manifest_version": 1,
        "change_class": "compatible",
        "current_program_id": "1" * 32,
        "proposed_program_id": "1" * 32,
        "current_protocol_version": 1,
        "proposed_protocol_version": 1,
        "current_binary_sha256": "sha256:" + "1" * 64,
        "proposed_binary_sha256": "sha256:" + "2" * 64,
        "source_commit": "3" * 40,
        "toolchain": "rustc 1.85.1",
        "lockfile_sha256": "sha256:" + "4" * 64,
        "current_account_layout_sha256": "sha256:" + "5" * 64,
        "proposed_account_layout_sha256": "sha256:" + "5" * 64,
        "current_instruction_registry_sha256": "sha256:" + "6" * 64,
        "proposed_instruction_registry_sha256": "sha256:" + "6" * 64,
        "current_signed_message_registry_sha256": "sha256:" + "7" * 64,
        "proposed_signed_message_registry_sha256": "sha256:" + "7" * 64,
        "approved_at": "2026-07-28T00:00:00Z",
        "earliest_execution_at": "2026-07-29T00:00:00Z",
        "authority_members": ["A" * 32, "B" * 32, "C" * 32],
        "threshold": 2,
        "approvals": ["A" * 32, "B" * 32],
        "execution_status": "not_executed",
        "verification_status": "not_performed",
    }
    Draft202012Validator(schema).validate(fixture)
    fixture["unexpected"] = True
    assert list(Draft202012Validator(schema).iter_errors(fixture))


def test_policy_forbids_single_wallet_and_preserves_rights() -> None:
    policy = load("governance-policy-v1.json")
    assert policy["production_authority"]["single_wallet_allowed"] is False
    assert policy["production_authority"]["minimum_threshold"] == 2
    assert policy["rights"] == {
        "activated_may_decrease_by_governance": False,
        "outstanding_may_be_redirected": False,
        "outstanding_and_unallocated_may_be_merged": False,
    }


def test_pause_blocks_ingress_but_preserves_safe_exits() -> None:
    operations = {
        row["operation"]: row["allowed_while_paused"]
        for row in load("emergency-pause-matrix.json")["operations"]
    }
    assert operations["initialize"] is False
    assert operations["fund"] is False
    assert operations["activate_voucher"] is False
    assert operations["settle_activated_right"] is True
    assert operations["refund_eligible_unallocated"] is True
    assert operations["finalize_resolved_channel"] is True
    assert operations["governance_sweep"] is False


def test_compatibility_and_migration_are_fail_closed() -> None:
    classes = load("compatibility-classification.json")
    assert "reinterpret_reserved_bytes" in classes["forbidden_over_v1"]
    assert "reduce_activated_right" in classes["forbidden_over_v1"]
    assert "changed_preimage" in classes["versioned"]

    migration = load("migration-matrix-v1.json")
    assert migration["default"] == "no_automatic_active_channel_migration"
    assert "outstanding_right" in migration["preserved_fields"]
    assert "unallocated_capacity" in migration["preserved_fields"]
    assert all(case["automatic"] is False for case in migration["cases"])


def test_timelock_and_authority_vectors_cover_boundaries() -> None:
    timelock = {row["id"]: row for row in load("timelock-vectors.json")["vectors"]}
    assert timelock["one_second_early"]["accepted"] is False
    assert timelock["exact_boundary"]["accepted"] is True
    assert timelock["checked_overflow"]["accepted"] is False

    authority = {row["id"]: row for row in load("authority-transition-vectors.json")["vectors"]}
    assert authority["two_of_three"]["accepted"] is True
    assert authority["one_of_three"]["accepted"] is False
    assert authority["unknown_approver"]["accepted"] is False
    assert authority["single_wallet"]["accepted"] is False


def test_deployment_is_blocked_and_build_verification_is_not_claimed() -> None:
    deployment = load("deployment-authorization.json")
    assert deployment["offline_model"] == "allowed"
    for target in ("local_validator", "devnet_fixture", "mainnet", "real_value"):
        assert deployment[target] == "blocked"
    assert deployment["external_review"] == "not_performed"
    build = load("reproducible-build-contract.json")
    assert build["deployed_build_reproduced"] is False
    assert build["verification_required_after_execution"] is True


def test_pinned_governance_model_passes() -> None:
    subprocess.run(
        [cargo(), "+1.85.1", "test", "--locked", "--manifest-path", str(MANIFEST)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
