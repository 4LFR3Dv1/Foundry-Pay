"""Executable FC-SEC-002 state-surface and rejection-effect taxonomy checks."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[4]
TAXONOMY_PATH = ROOT / "docs/channels/security/FC-SEC-002/state-surface-taxonomy.yaml"
DOMAINS_PATH = ROOT / "contracts/channel/canonicalization/domains.v1.json"


def load_taxonomy() -> dict[str, object]:
    return yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))


def test_effect_allowlist_never_grants_authority_or_economic_effect() -> None:
    taxonomy = load_taxonomy()
    permitted = taxonomy["permitted_rejection_effects"]

    assert permitted
    for effect in permitted:
        assert effect["authority_effect"] is False
        assert effect["economic_effect"] is False
        assert effect["lifecycle_effect"] is False
        assert effect["normative_sequence_effect"] is False

    assert taxonomy["effect_classes"]["local_rate_limit"]["rejection_policy"] == (
        "undeclared_and_forbidden_in_v1"
    )


def test_direct_signed_domains_match_frozen_registry() -> None:
    taxonomy = load_taxonomy()
    registry = json.loads(DOMAINS_PATH.read_text(encoding="utf-8"))
    domains = {entry["domain"]: entry for entry in registry["domains"]}
    objects = taxonomy["objects"]

    voucher = objects["channel_voucher"]
    binding = objects["recipient_binding"]

    assert domains[voucher["registry_domain"]]["profile_id"] == "signed-payload-v1"
    assert domains[binding["registry_domain"]]["profile_id"] == "signed-payload-v1"
    assert voucher["authority_binding"] == "direct_exact_payload_signature"
    assert binding["authority_binding"] == "direct_dual_exact_payload_signature"


def test_hashes_and_receipts_are_not_misrepresented_as_signatures() -> None:
    objects = load_taxonomy()["objects"]

    assert objects["settlement_request"]["limitation"] == ("request hash alone is not a signature")
    assert objects["settlement_execution_commitment"]["limitation"] == (
        "commitment hash alone is not a signature"
    )
    assert objects["channel_closure_request"]["signer"] == (
        "not_present_in_offline_reference_object"
    )
    assert objects["reconciled_receipt"]["authority_binding"] == (
        "non_authoritative_reconciliation_evidence"
    )


def test_rejection_behavior_is_closed_for_every_inventory_object() -> None:
    objects = load_taxonomy()["objects"]
    expected_fields = {
        "economic_effect",
        "authority_advancement",
        "lifecycle_transition",
        "normative_sequence_effect",
        "audit_append",
    }

    for object_name, item in objects.items():
        behavior = item["rejection_behavior"]
        assert set(behavior) in (
            expected_fields,
            expected_fields | {"audit_event_type"},
        ), object_name
        assert behavior["economic_effect"] == "forbidden"
        assert behavior["authority_advancement"] == "forbidden"
        assert behavior["lifecycle_transition"] == "forbidden"
        assert behavior["normative_sequence_effect"] == "forbidden"
        if behavior["audit_append"] == "permitted":
            assert behavior["audit_event_type"] == "rejected"


def test_forbidden_effects_cover_normative_and_money_moving_state() -> None:
    forbidden = set(load_taxonomy()["forbidden_rejection_effects"])

    assert {
        "advance_latest_sequence",
        "replace_latest_voucher_hash",
        "consume_binding_nonce",
        "consume_execution_authorization",
        "create_pending_settlement",
        "bind_recipient",
        "activate_right",
        "authorize_execution",
        "settle_value",
        "close_or_finalize_channel",
    } <= forbidden
