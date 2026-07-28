from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-003A"


def load(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_initialize_has_atomic_creation_program_metas() -> None:
    contracts = load("account-meta-contracts-v1.json")
    initialize = next(item for item in contracts if item["instruction"] == "initialize_channel")
    by_name = {account["name"]: account for account in initialize["accounts"]}
    assert set(by_name) == {
        "channel",
        "sender",
        "mint",
        "vault",
        "system_program",
        "token_program",
        "associated_token_program",
    }
    assert by_name["sender"]["signer"] is True
    assert by_name["sender"]["writable"] is True
    assert by_name["system_program"]["address_rule"] == "solana_system_program_id"
    assert by_name["token_program"]["address_rule"] == "classic_spl_token_program_id"
    assert by_name["associated_token_program"]["address_rule"] == "spl_associated_token_program_id"


def test_settlement_is_permissionless_with_fixed_destination() -> None:
    registry = load("instruction-registry-v1.json")
    settlement = next(item for item in registry if item["name"] == "settle")
    assert settlement["authority"] == "PermissionlessBoundRecipientSettlement"

    contracts = load("account-meta-contracts-v1.json")
    accounts = next(item for item in contracts if item["instruction"] == "settle")["accounts"]
    assert not any(account["signer"] for account in accounts)
    destination = next(
        account for account in accounts if account["name"] == "recipient_token_account"
    )
    assert destination["address_rule"] == ("canonical_ata(bound_recipient_wallet,channel_mint)")


def test_claim_window_is_bounded_and_checked() -> None:
    lifecycle = load("lifecycle-transition-matrix-v1.json")
    assert lifecycle["minimum_claim_window_seconds"] == 900
    assert lifecycle["maximum_claim_window_seconds"] == 2_592_000
    assert lifecycle["deadline_is_exclusive"] is True
    assert lifecycle["deadline_arithmetic"] == "checked"
    negative_cases = {item["case"] for item in load("negative-vectors-v1.json")}
    assert {"claim_deadline_too_soon", "claim_deadline_too_late"} <= negative_cases


def test_frozen_byte_contracts_are_unchanged() -> None:
    report = load("compatibility-report.json")
    assert report["instruction_serialization_byte_identical"] is True
    assert report["ed25519_layouts_byte_identical"] is True
    assert report["signed_message_mapping_unchanged"] is True
    assert report["channel_state_layout_bytes"] == 490
    assert report["pda_derivation_changed"] is False


def test_operability_artifact_manifest_recalculates() -> None:
    manifest = load("artifact-manifest.json")
    assert manifest["artifact_count"] == len(manifest["artifacts"])
    for artifact in manifest["artifacts"]:
        raw = (ROOT / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert f"sha256:{hashlib.sha256(raw).hexdigest()}" == artifact["sha256"]
