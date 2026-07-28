"""Executable checks for the Foundry Channels foundation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import yaml


ROOT = Path(__file__).parents[2]


def load_checker() -> ModuleType:
    path = ROOT / "scripts" / "check_channel_foundation.py"
    spec = importlib.util.spec_from_file_location("check_channel_foundation", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_foundation_contracts_and_gates_pass() -> None:
    result = load_checker().validate()

    assert result["status"] == "passed", result["errors"]
    assert result["checks"]["schemas"]["count"] == 7
    assert result["checks"]["negative_vectors"]["count"] >= 12
    assert result["checks"]["closing_race_vector"]["valid"] is True
    assert result["checks"]["closing_race_vector"]["validated_objects"] == [
        "closure_request",
        "snapshot_at_request",
        "snapshot_at_freeze",
    ]
    assert (
        result["checks"]["closing_race_vector"]["rules"]["freeze_refund_uses_final_activation"]
        is True
    )
    assert result["checks"]["work_graph"]["ready_items"] == [
        "FC-FAIL-003",
        "FC-SEC-004",
        "FC-SOL-005",
        "FC-VAL-003",
        "SA-CHAN-001",
    ]
    assert result["checks"]["work_graph"]["ready_with_incomplete_dependencies"] == {}
    assert result["checks"]["accounting"] == {
        "conservation": True,
        "rights_bounds": True,
    }


def test_fc_proto_007_integration_uses_governed_self_validation() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    conformance = by_id["FC-PROTO-007"]
    assert conformance["status"] == "done"
    assert conformance["implementation"] == {
        "pr": 34,
        "functional_head": "ef9a99949bae3d2088a7b51cd55ef4efb14124c7",
        "evidence_head": "5e4f7fff521f99c93a2e6b99bd8db8c9a8041649",
        "merge_commit": "63da85549bcd247a0510e8af18cddc30d8c53bb2",
        "main_ci_run": 30286605271,
    }
    assert conformance["maturity"] == {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
        "local_validator": "allowed",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }

    assert by_id["FC-SEC-002"]["status"] == "done"
    assert by_id["SA-CHAN-000"]["status"] == "done"
    assert by_id["SA-CHAN-000"]["dependencies"] == [
        "FC-PROTO-007",
        "FC-SEC-002",
        "FC-CTRL-021",
    ]


def test_fc_sec_002_contract_matches_governed_experimental_scope() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    assert by_id["FC-CTRL-015"]["status"] == "done"
    assert by_id["FC-CTRL-016"]["status"] == "done"

    security = by_id["FC-SEC-002"]
    assert security["status"] == "done"
    assert security["implementation"] == {
        "pr": 40,
        "functional_head": "e785dedd62b982cbe03a7b542534688ddc3b8370",
        "evidence_head": "dc0ff464a54044144a836af762d84c839b58cb2f",
        "merge_commit": "0d203389052a78d6cdec5b565ca28e605dad13fb",
        "main_ci_run": 30310413080,
    }
    assert security["maturity"] == {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
        "local_validator": "allowed",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }
    assert security["dependencies"] == [
        "FC-PROTO-002",
        "FC-PROTO-006",
        "FC-PROTO-007",
        "FC-CTRL-017",
    ]
    assert security["maturity_gate"] == {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
    }
    assert security["deployment_authorization"] == {
        "local_validator": "allowed",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }
    assert security["external_review_requirement"] == {"required_before": ["mainnet", "real_value"]}
    assert "Cloud statements cannot revoke cryptographic rights" in security["invariants"]
    assert (
        "rejected mutations create no economic effect or authority advancement"
        in security["invariants"]
    )
    assert (
        "durable rejection audit effects are permitted but never confer authority"
        in security["invariants"]
    )
    assert (
        "an unknown version or profile falls back to an older interpretation"
        in security["stop_conditions"]
    )
    assert (
        "a rejected mutation advances verified, activation-requested, authorized, or completed state"
        in security["stop_conditions"]
    )

    task = yaml.safe_load((ROOT / ".agents/tasks/FC-SEC-002.yaml").read_text(encoding="utf-8"))
    assert task["dependencies"] == security["dependencies"]

    assert by_id["FC-SOL-002"]["status"] == "done"
    assert by_id["FC-SOL-003"]["status"] == "done"
    assert by_id["FC-SOL-004"]["status"] == "done"
    assert by_id["SA-CHAN-000"]["status"] == "done"
    assert by_id["FC-FAIL-003"]["status"] == "ready"


def test_fc_sol_002_contract_is_fixed_width_and_local_validator_only() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    assert by_id["FC-CTRL-020"]["status"] == "done"

    account_model = by_id["FC-SOL-002"]
    assert account_model["status"] == "done"
    assert account_model["dependencies"] == ["FC-PROTO-001", "FC-SEC-002"]
    assert account_model["maturity_gate"] == {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
    }
    assert account_model["deployment_authorization"] == {
        "local_validator": "allowed",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }
    assert account_model["external_review_requirement"] == {
        "required_before": ["mainnet", "real_value"]
    }
    assert (
        "the only state topology is one ChannelState PDA plus its vault token account"
        in account_model["invariants"]
    )
    assert (
        "classic SPL Token is allowlisted and Token-2022 is unsupported"
        in account_model["invariants"]
    )

    task = yaml.safe_load((ROOT / ".agents/tasks/FC-SOL-002.yaml").read_text(encoding="utf-8"))
    assert task["dependencies"] == account_model["dependencies"]
    assert task["maturity_gate"] == account_model["maturity_gate"]
    assert task["deployment_authorization"] == account_model["deployment_authorization"]
    assert task["external_review_requirement"] == account_model["external_review_requirement"]

    contract = (ROOT / "docs/channels/solana/accounts/FC-SOL-002-CONTRACT.md").read_text(
        encoding="utf-8"
    )
    assert "ChannelState PDA" in contract
    assert "classic SPL Token vault account" in contract
    assert "String" in contract and "Vec<T>" in contract and "Option<T>" in contract
    assert "Token-2022" in contract
    assert "performs no token transfer or CPI" in contract

    assert by_id["FC-SOL-003"]["status"] == "done"
    assert by_id["FC-SOL-004"]["status"] == "done"
    assert by_id["FC-FAIL-003"]["status"] == "ready"


def test_sa_chan_000_contract_is_offline_authority_free_and_adversarial() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    assert by_id["FC-CTRL-021"]["status"] == "done"

    fake_adapter = by_id["SA-CHAN-000"]
    assert fake_adapter["status"] == "done"
    assert fake_adapter["dependencies"] == [
        "FC-PROTO-007",
        "FC-SEC-002",
        "FC-CTRL-021",
    ]
    assert fake_adapter["maturity_gate"] == {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
    }
    assert fake_adapter["deployment_authorization"] == {
        "offline_fixture": "allowed",
        "local_validator": "not_required",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }
    assert (
        "technical confirmation is distinct from independently reconciled economic completion"
        in fake_adapter["invariants"]
    )
    assert (
        "unknown submission results never trigger automatic retry or rematerialization"
        in fake_adapter["invariants"]
    )

    task = yaml.safe_load((ROOT / ".agents/tasks/SA-CHAN-000.yaml").read_text(encoding="utf-8"))
    assert task["dependencies"] == fake_adapter["dependencies"]
    assert task["maturity_gate"] == fake_adapter["maturity_gate"]
    assert task["deployment_authorization"] == fake_adapter["deployment_authorization"]

    contract = (ROOT / "docs/channels/capabilities/SA-CHAN-000-CONTRACT.md").read_text(
        encoding="utf-8"
    )
    assert "technical confirmation" in contract
    assert "independent observation" in contract
    assert "reconciled economic completion" in contract
    assert "automatic second submission count = 0" in contract
    assert "This is not an exactly-once blockchain claim." in contract

    assert by_id["SA-CHAN-001"]["status"] == "ready"
    assert by_id["SA-CHAN-002"]["status"] == "blocked"
    assert by_id["SA-CHAN-003"]["status"] == "blocked"
    assert by_id["SA-CHAN-004"]["status"] == "blocked"


def test_fc_sol_003_contract_freezes_authority_without_runtime_or_deployment() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    assert by_id["FC-CTRL-023"]["status"] == "done"
    instruction_contract = by_id["FC-SOL-003"]
    assert instruction_contract["status"] == "done"
    assert instruction_contract["dependencies"] == [
        "FC-PROTO-002",
        "FC-PROTO-003",
        "FC-PROTO-004",
        "FC-PROTO-005",
        "FC-SOL-002",
        "FC-SEC-002",
    ]
    assert instruction_contract["maturity_gate"] == {
        "implementation": "complete",
        "self_validation": "passed",
        "external_review": "not_performed",
    }
    assert instruction_contract["deployment_authorization"] == {
        "local_fixture": "allowed",
        "local_validator": "allowed",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }
    assert instruction_contract["external_review_requirement"] == {
        "required_before": ["devnet_fixture", "mainnet", "real_value"]
    }

    task = yaml.safe_load((ROOT / ".agents/tasks/FC-SOL-003.yaml").read_text(encoding="utf-8"))
    assert task["dependencies"] == instruction_contract["dependencies"]
    assert task["maturity_gate"] == instruction_contract["maturity_gate"]
    assert task["deployment_authorization"] == instruction_contract["deployment_authorization"]

    contract = (ROOT / "docs/channels/solana/instructions/FC-SOL-003-CONTRACT.md").read_text(
        encoding="utf-8"
    )
    for instruction in (
        "initialize_channel",
        "fund_channel",
        "activate_voucher",
        "bind_recipient",
        "settle",
        "request_close",
        "refund_unallocated",
        "finalize_close",
    ):
        assert f"`{instruction}`" in contract
    assert "immediately preceding" in contract
    assert "every instruction-index field is\n`u16::MAX`" in contract
    assert "total length = H + 192 + (2 * M)" in contract
    assert "closing_open" in contract and "closing_frozen" in contract
    assert "The claim deadline is exclusive" in contract
    assert "490-byte `ChannelState`" in contract
    assert "does **not** implement an entrypoint" in contract
    assert "Token-2022" in contract

    assert by_id["FC-SOL-004"]["status"] == "done"
    assert by_id["FC-SOL-005"]["status"] == "ready"
    assert by_id["SA-CHAN-001"]["status"] == "ready"

    coordination = by_id["FC-CTRL-024"]
    assert coordination["status"] == "done"
    report = json.loads(
        (ROOT / "evidence/runs/FC-CTRL-024/validation-report.json").read_text(encoding="utf-8")
    )
    assert report["fc_sol_003"]["functional_head"] == ("2b6b5e4c8440571bf49f7917a088f861fd46d46e")
    assert report["fc_sol_003"]["evidence_head"] == ("097a03c99ad4a0fb27827fc655b0ff775675480a")
    assert report["fc_sol_003"]["merge_commit"] == ("192bd40245244cfd540c67f880104259b5190379")
    assert report["fc_sol_003"]["main_ci_run"] == 30371165634
    assert report["fc_sol_003"]["external_review"] == "not_performed"
    assert report["fc_sol_003"]["deployment_authorization"]["devnet_fixture"] == "blocked"
    assert report["fc_sol_003"]["deployment_authorization"]["mainnet"] == "blocked"
    assert report["fc_sol_003"]["deployment_authorization"]["real_value"] == "blocked"


def test_fc_sol_003a_preflight_freezes_operable_authority_and_deadline_rules() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    correction = by_id["FC-SOL-003A"]
    assert correction["status"] == "done"
    assert correction["dependencies"] == ["FC-SOL-003", "FC-CTRL-025"]
    assert by_id["FC-SOL-004"]["status"] == "done"
    assert by_id["FC-SOL-004"]["dependencies"] == [
        "FC-SOL-003A",
        "FC-SEC-002",
        "FC-CTRL-027",
    ]
    assert by_id["SA-CHAN-001"]["status"] == "ready"
    assert by_id["SA-CHAN-001"]["dependencies"] == ["FC-PROTO-006", "FC-SOL-003A"]
    assert by_id["FC-SOL-005"]["status"] == "ready"
    assert by_id["FC-FAIL-003"]["status"] == "ready"

    adr = (ROOT / "docs/channels/ADR/FC-ADR-010-channelvault-v1-operability.md").read_text(
        encoding="utf-8"
    )
    assert "System Program CPI using `invoke_signed`" in adr
    assert "Associated Token Program" in adr
    assert "Protocol v1 settlement is permissionless" in adr
    assert "MIN_CLAIM_WINDOW_SECONDS = 900" in adr
    assert "MAX_CLAIM_WINDOW_SECONDS = 2_592_000" in adr

    report = json.loads(
        (ROOT / "evidence/runs/FC-CTRL-025/validation-report.json").read_text(encoding="utf-8")
    )
    assert report["runtime_changes"] == 0
    assert report["external_review"] == "not_performed"
    assert report["decisions"]["minimum_claim_window_seconds"] == 900
    assert report["decisions"]["maximum_claim_window_seconds"] == 2_592_000

    integration = json.loads(
        (ROOT / "evidence/runs/FC-CTRL-026/validation-report.json").read_text(encoding="utf-8")
    )
    assert integration["fc_sol_003a"]["functional_head"] == (
        "db1aeecc0ebc3777aac70fad998a92f7d511c41c"
    )
    assert integration["fc_sol_003a"]["evidence_head"] == (
        "7a3a28b458f4e461748d43821887b8904b299393"
    )
    assert integration["fc_sol_003a"]["merge_commit"] == (
        "aaffd54d0712dc7b0add981d06923dab00e4aba1"
    )
    assert integration["fc_sol_003a"]["main_ci_run"] == 30375043779


def test_fc_sol_004_preflight_freezes_precise_model_claims() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}

    assert by_id["FC-CTRL-027"]["status"] == "done"
    model = by_id["FC-SOL-004"]
    assert model["status"] == "done"
    assert model["dependencies"] == ["FC-SOL-003A", "FC-SEC-002", "FC-CTRL-027"]
    assert model["maturity_gate"]["external_review"] == "not_performed"
    assert model["deployment_authorization"] == {
        "pure_model": "allowed",
        "local_validator": "blocked",
        "devnet_fixture": "blocked",
        "mainnet": "blocked",
        "real_value": "blocked",
    }

    adr = (ROOT / "docs/channels/ADR/FC-ADR-011-transition-model-preflight.md").read_text(
        encoding="utf-8"
    )
    assert "absent_or_system_owned_zero_data" in adr
    assert "caller-supplied opaque correlation value" in adr
    assert "not formal verification" in adr

    task = yaml.safe_load((ROOT / ".agents/tasks/FC-SOL-004.yaml").read_text(encoding="utf-8"))
    assert task["dependencies"] == model["dependencies"]
    assert task["maturity_gate"] == model["maturity_gate"]
    assert task["deployment_authorization"] == model["deployment_authorization"]

    report = json.loads(
        (ROOT / "evidence/runs/FC-CTRL-027/validation-report.json").read_text(encoding="utf-8")
    )
    assert report["runtime_changes"] == 0
    assert report["decisions"]["formal_verification_claimed"] is False
    assert report["decisions"]["obligation_hash"] == (
        "caller_supplied_non_authoritative_correlation"
    )


def test_fc_sol_004_integration_releases_only_concurrency_model_work() -> None:
    work_items = yaml.safe_load(
        (ROOT / "docs/channels/work-items.yaml").read_text(encoding="utf-8")
    )["work_items"]
    by_id = {item["id"]: item for item in work_items}
    assert by_id["FC-SOL-004"]["status"] == "done"
    assert by_id["FC-SEC-004"]["status"] == "ready"
    assert by_id["FC-SOL-005"]["status"] == "ready"
    assert by_id["SA-CHAN-001"]["status"] == "ready"
    assert by_id["FC-FAIL-003"]["status"] == "ready"
    assert by_id["SA-CHAN-002"]["status"] == "blocked"

    report = json.loads(
        (ROOT / "evidence/runs/FC-CTRL-029/validation-report.json").read_text(encoding="utf-8")
    )
    integration = report["fc_sol_004"]
    assert integration["functional_head"] == ("da8baf5f008653f771c589adfa79f82503e1e2b4")
    assert integration["evidence_head"] == ("0efc701d54dba140c784b77555afd076f09d5777")
    assert integration["merge_commit"] == ("3f1740e70abb9ee67f7b83130fa5aef2a76befb8")
    assert integration["main_ci_run"] == 30379326962
    assert integration["invariant_violations"] == 0
    assert integration["formal_verification"] == "not_performed"
    assert integration["external_review"] == "not_performed"
    assert report["released"] == ["FC-SEC-004"]
