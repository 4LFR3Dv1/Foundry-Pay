from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-004"


def load(name: str) -> object:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_owner_transition_and_settlement_correlation_are_explicit() -> None:
    contracts = load("account-meta-contracts-v1.json")
    initialize = next(item for item in contracts if item["instruction"] == "initialize_channel")
    channel = next(account for account in initialize["accounts"] if account["name"] == "channel")
    assert channel["pre_owner_rule"] == "absent_or_system_owned_zero_data"
    assert channel["post_owner_rule"] == "foundry_channel_vault_program"

    registry = load("instruction-registry-v1.json")
    settle = next(item for item in registry if item["name"] == "settle")
    assert settle["authority"] == "PermissionlessBoundRecipientSettlement"
    assert settle["correlation_policy"] == (
        "obligation_hash:caller_supplied_non_authoritative_correlation"
    )
    assert settle["runtime_handler_implemented"] is False


def test_transition_validation_reports_zero_violations_with_narrow_claims() -> None:
    report = load("validation-report.json")
    assert report["model_operations"] == 8
    assert report["property_cases"] == 1536
    assert report["bounded_exploration"]["attempted_transitions"] == 4732
    assert report["bounded_exploration"]["visited_states"] == 703
    assert report["bounded_exploration"]["invariant_violations"] == 0
    assert report["formal_verification"] == "not_performed"
    assert report["runtime_program_implemented"] is False
    assert report["external_review"] == "not_performed"
    assert report["deployment_authorization"]["local_validator"] == "blocked"
    assert report["deployment_authorization"]["devnet_fixture"] == "blocked"
    assert report["deployment_authorization"]["mainnet"] == "blocked"
    assert report["deployment_authorization"]["real_value"] == "blocked"


def test_permissionless_settlement_has_no_caller_or_correlation_authority() -> None:
    report = load("settlement-authority-report.json")
    assert report["caller_identity_economic_effect"] is False
    assert report["obligation_hash_economic_effect"] is False
    assert report["obligation_hash_business_outcome_proof"] is False
    assert report["result"] == "passed"


def test_artifact_manifest_reproduces_every_published_hash() -> None:
    manifest = load("artifact-manifest.json")
    assert manifest["implementation_commit"] == ("da8baf5f008653f771c589adfa79f82503e1e2b4")
    assert len(manifest["artifacts"]) >= 18
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["bytes"]
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == artifact["sha256"]


def test_pinned_rust_model_and_bounded_explorer_reproduce() -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        executable = "cargo.exe" if os.name == "nt" else "cargo"
        candidate = Path.home() / ".cargo/bin" / executable
        if candidate.exists():
            cargo = str(candidate)
    assert cargo is not None, "cargo is required for FC-SOL-004 self-validation"

    model_root = ROOT / "programs/foundry-channel-vault/transition-model"
    subprocess.run(
        [cargo, "test", "--locked"],
        cwd=model_root,
        check=True,
        capture_output=True,
        text=True,
    )
    with tempfile.TemporaryDirectory() as temporary:
        report_path = Path(temporary) / "bounded.json"
        subprocess.run(
            [
                cargo,
                "run",
                "--locked",
                "--example",
                "bounded_explorer",
                "--",
                str(report_path),
            ],
            cwd=model_root,
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["visited_states"] == 703
    assert report["attempted_transitions"] == 4732
    assert report["invariant_violations"] == 0
