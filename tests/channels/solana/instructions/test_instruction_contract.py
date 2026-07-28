from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-003"
RUST_MANIFEST = ROOT / "programs/foundry-channel-vault/instruction-contract/Cargo.toml"


def load(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_eight_atomic_instruction_contracts_are_closed() -> None:
    registry = load("instruction-registry-v1.json")
    assert [item["name"] for item in registry] == [
        "initialize_channel",
        "fund_channel",
        "activate_voucher",
        "bind_recipient",
        "settle",
        "request_close",
        "refund_unallocated",
        "finalize_close",
    ]
    assert all(item["runtime_handler_implemented"] is False for item in registry)
    assert len({item["discriminator_hex"] for item in registry}) == 8


def test_account_contracts_close_authority_and_token_boundary() -> None:
    contracts = load("account-meta-contracts-v1.json")
    by_name = {item["instruction"]: item["accounts"] for item in contracts}
    assert any(account["signer"] for account in by_name["initialize_channel"])
    assert any(account["name"] == "instructions_sysvar" for account in by_name["activate_voucher"])
    assert any(account["name"] == "instructions_sysvar" for account in by_name["bind_recipient"])
    for name in ("fund_channel", "settle", "refund_unallocated"):
        token = next(account for account in by_name[name] if account["name"] == "token_program")
        assert token["address_rule"] == "classic_spl_token_program_id"


def test_ed25519_offsets_and_program_are_exact() -> None:
    vectors = load("ed25519-offset-vectors-v1.json")
    assert vectors["program_id"] == "Ed25519SigVerify111111111111111111111111111"
    assert vectors["instruction_position"] == "immediately_preceding"
    assert vectors["instruction_references"] == "u16::MAX_self_contained_only"
    assert vectors["voucher"]["public_key_offset"] == 16
    assert vectors["voucher"]["signature_offset"] == 48
    assert vectors["voucher"]["message_offset"] == 112
    assert vectors["binding"]["header_length"] == 30
    assert vectors["binding"]["messages_overlap"] is False
    assert vectors["binding"]["total_length"] == (222 + 2 * vectors["binding"]["message_length"])


def test_lifecycle_is_derived_without_layout_change() -> None:
    lifecycle = load("lifecycle-transition-matrix-v1.json")
    assert lifecycle["layout_changed"] is False
    assert lifecycle["deadline_is_exclusive"] is True
    assert lifecycle["activated_rights_expire"] is False
    finalized = next(item for item in lifecycle["phases"] if item["phase"] == "finalized")
    assert finalized["terminal"] is True


def test_negative_vectors_project_no_transition_or_success_event() -> None:
    negatives = load("negative-vectors-v1.json")
    required = {
        "account_substitution",
        "token_2022",
        "sequence_replay",
        "binding_nonce_replay",
        "ed25519_external_reference",
        "ed25519_offset_mutated",
        "ed25519_pubkey_mutated",
        "preimage_one_byte_mutated",
    }
    assert required <= {item["case"] for item in negatives}
    assert all(item["decision"] == "rejected" for item in negatives)
    assert all(item["projected_transition_count"] == 0 for item in negatives)
    assert all(item["success_event_count"] == 0 for item in negatives)


def test_instruction_bytes_and_registry_hashes_reproduce() -> None:
    serialization = load("instruction-serialization-v1.json")
    for vector in serialization:
        raw = bytes.fromhex(vector["bytes_hex"])
        assert len(raw) == vector["byte_length"]
        assert f"sha256:{hashlib.sha256(raw).hexdigest()}" == vector["sha256"]

    report = load("idl-hash-report.json")
    assert report["anchor_idl_generated"] is False
    assert report["deployable_entrypoint_exists"] is False
    for artifact in report["artifacts"]:
        raw = (EVIDENCE / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert f"sha256:{hashlib.sha256(raw).hexdigest()}" == artifact["sha256"]


def test_events_are_facts_not_business_outcomes() -> None:
    events = load("event-registry-v1.json")
    assert len(events) == 8
    assert all(event["business_completion_claim"] is False for event in events)
    names = {event["name"] for event in events}
    assert "PaymentCompleted" not in names
    assert "BusinessObligationSatisfied" not in names


def test_artifact_manifest_recalculates() -> None:
    manifest = load("artifact-manifest.json")
    assert len(manifest["functional_head"]) == 40
    assert all(character in "0123456789abcdef" for character in manifest["functional_head"])
    assert manifest["artifact_count"] == len(manifest["artifacts"])
    for artifact in manifest["artifacts"]:
        raw = (ROOT / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert f"sha256:{hashlib.sha256(raw).hexdigest()}" == artifact["sha256"]


def test_rust_contract_crate_passes_locked_suite() -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    subprocess.run(
        [cargo, "test", "--locked", "--manifest-path", str(RUST_MANIFEST), "--lib"],
        cwd=ROOT,
        check=True,
    )
