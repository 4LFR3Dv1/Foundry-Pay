"""Executable checks for the Foundry Channels foundation."""

from __future__ import annotations

import importlib.util
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
        "FC-SOL-003",
        "FC-VAL-003",
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
    assert by_id["FC-SOL-003"]["status"] == "ready"
    assert by_id["FC-SOL-004"]["status"] == "blocked"
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

    assert by_id["FC-SOL-003"]["status"] == "ready"
    assert by_id["FC-SOL-004"]["status"] == "blocked"
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

    assert by_id["SA-CHAN-001"]["status"] == "blocked"
    assert by_id["SA-CHAN-002"]["status"] == "blocked"
    assert by_id["SA-CHAN-003"]["status"] == "blocked"
    assert by_id["SA-CHAN-004"]["status"] == "blocked"
