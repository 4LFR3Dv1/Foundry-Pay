from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from services.reconciliation import (
    ObservationSource,
    ReconciliationInvalid,
    SourceDescriptor,
    SourceRegistry,
    TransactionSnapshot,
    aggregate_reconciliation,
    endpoint_identity_hash,
    normalize_observation,
    observation_hash,
)
from services.reconciliation.backfill import backfill_fp_e2e_001

ROOT = Path(__file__).parents[2]
PROOF = ROOT / "evidence" / "runs" / "FP-E2E-001" / "live-proof.json"
LIVE_EVIDENCE = ROOT / "evidence" / "runs" / "FP-REC-001"
SCHEMA = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "schemas"
    / "reconciliation-observation.v1.schema.json"
)
VALIDATOR = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


@pytest.fixture
def live() -> tuple[dict, dict, SourceDescriptor]:
    return backfill_fp_e2e_001(PROOF)


def independent_descriptor(
    *,
    source_id: str = "provider_b_devnet",
    source_class: str = "L2",
    source_kind: str = "rpc",
    provider_id: str = "provider_b",
    trust_domain_id: str = "provider_b_infra",
    endpoint: str = "https://devnet.provider-b.example",
    parser_id: str = "provider_b_parser_v1",
) -> SourceDescriptor:
    return SourceDescriptor(
        source_id=source_id,
        source_class=source_class,  # type: ignore[arg-type]
        source_kind=source_kind,  # type: ignore[arg-type]
        provider_id=provider_id,
        trust_domain_id=trust_domain_id,
        endpoint_identity_hash=endpoint_identity_hash(endpoint),
        parser_id=parser_id,
    )


def from_source(observation: dict, descriptor: SourceDescriptor) -> dict:
    changed = copy.deepcopy(observation)
    for field, value in descriptor.__dict__.items():
        changed[field] = value
    changed["queried_at"] = "2026-07-23T21:00:00Z"
    changed["raw_response_hash"] = "sha256:" + "b" * 64
    return normalize_observation(changed)


def test_live_fp_e2e_backfills_to_hashed_schema_valid_l1(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, observation, descriptor = live

    assert list(VALIDATOR.iter_errors(observation)) == []
    assert observation["source_class"] == "L1"
    assert observation["observed_amount_base_units"] == "1000000"
    assert observation_hash(observation).startswith("sha256:")

    result = aggregate_reconciliation(
        expected,
        [observation],
        SourceRegistry([descriptor]),
    )
    assert result["execution_status"] == "confirmed"
    assert result["reconciliation_status"] == "l1_verified"
    assert result["independent_verification"] == "pending"
    assert result["consensus"] == "approved"


def test_committed_live_l2_bundle_is_valid_and_approved() -> None:
    expected, _, _ = backfill_fp_e2e_001(PROOF)
    l1 = json.loads((LIVE_EVIDENCE / "l1-observation.json").read_text(encoding="utf-8"))
    l2 = json.loads((LIVE_EVIDENCE / "l2-observation.json").read_text(encoding="utf-8"))
    stored_result = json.loads(
        (LIVE_EVIDENCE / "reconciliation-result.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((LIVE_EVIDENCE / "manifest.json").read_text(encoding="utf-8"))

    assert list(VALIDATOR.iter_errors(l1)) == []
    assert list(VALIDATOR.iter_errors(l2)) == []
    descriptors = [
        SourceDescriptor(
            **{
                field: observation[field]
                for field in (
                    "source_id",
                    "source_class",
                    "source_kind",
                    "provider_id",
                    "trust_domain_id",
                    "endpoint_identity_hash",
                    "parser_id",
                )
            }
        )
        for observation in (l1, l2)
    ]
    result = aggregate_reconciliation(
        expected,
        [l1, l2],
        SourceRegistry(descriptors),
    )

    assert result == stored_result
    assert result["execution_status"] == "finalized"
    assert result["independent_verification"] == "l2_verified"
    assert descriptors[0].provider_id != descriptors[1].provider_id
    assert descriptors[0].trust_domain_id != descriptors[1].trust_domain_id
    assert descriptors[0].endpoint_identity_hash != descriptors[1].endpoint_identity_hash
    assert manifest["observation_hashes"] == {
        "L1": observation_hash(l1),
        "L2": observation_hash(l2),
    }


def test_hash_ignores_property_order_but_detects_single_field_tamper(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    _, observation, _ = live
    reordered = dict(reversed(list(observation.items())))
    assert observation_hash(reordered) == observation_hash(observation)

    tampered = copy.deepcopy(observation)
    tampered["slot"] += 1
    assert observation_hash(tampered) != observation_hash(observation)


def test_diverse_agreeing_l2_upgrades_independent_verification(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, l1_descriptor = live
    l2_descriptor = independent_descriptor()
    l2 = from_source(l1, l2_descriptor)

    result = aggregate_reconciliation(
        expected,
        [l1, l2],
        SourceRegistry([l1_descriptor, l2_descriptor]),
    )

    assert result["reconciliation_status"] == "l1_verified"
    assert result["independent_verification"] == "l2_verified"
    assert result["consensus"] == "approved"


def test_same_provider_or_endpoint_cannot_count_as_l2(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, l1_descriptor = live
    l2_descriptor = independent_descriptor(
        provider_id=l1_descriptor.provider_id,
        endpoint="https://api.devnet.solana.com",
    )
    l2 = from_source(l1, l2_descriptor)

    result = aggregate_reconciliation(
        expected,
        [l1, l2],
        SourceRegistry([l1_descriptor, l2_descriptor]),
    )

    assert result["independent_verification"] == "pending"


def test_observation_cannot_self_assert_registered_source_metadata(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, l1_descriptor = live
    forged = copy.deepcopy(l1)
    forged["provider_id"] = "forged_provider"

    with pytest.raises(ReconciliationInvalid, match="does not match registry"):
        aggregate_reconciliation(
            expected,
            [forged],
            SourceRegistry([l1_descriptor]),
        )


def test_qualifying_l3_upgrades_without_blocking_on_l2(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, l1_descriptor = live
    l3_descriptor = independent_descriptor(
        source_id="independent_indexer",
        source_class="L3",
        source_kind="indexer",
        provider_id="indexer_operator",
        trust_domain_id="indexer_pipeline",
        endpoint="https://indexer.example/solana/devnet",
        parser_id="indexer_parser_v1",
    )
    l3 = from_source(l1, l3_descriptor)

    result = aggregate_reconciliation(
        expected,
        [l1, l3],
        SourceRegistry([l1_descriptor, l3_descriptor]),
    )
    assert result["independent_verification"] == "l3_verified"


def test_material_disagreement_opens_dispute_without_reversing_confirmation(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, l1_descriptor = live
    l2_descriptor = independent_descriptor()
    l2 = from_source(l1, l2_descriptor)
    l2["source_account_after"] = "98000000"
    l2["destination_account_after"] = "2000000"
    l2["observed_amount_base_units"] = "2000000"
    l2 = normalize_observation(l2)

    result = aggregate_reconciliation(
        expected,
        [l1, l2],
        SourceRegistry([l1_descriptor, l2_descriptor]),
    )

    assert result["execution_status"] == "confirmed"
    assert result["reconciliation_status"] == "reconciliation_disputed"
    assert result["independent_verification"] == "disputed"
    assert result["consensus"] == "disputed"
    assert result["observations"][1]["disagreements"] == ["amount_base_units"]


def test_unavailable_l2_remains_pending(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, descriptor = live
    result = aggregate_reconciliation(
        expected,
        [l1],
        SourceRegistry([descriptor]),
        unavailable_source_ids=["provider_b_devnet"],
    )
    assert result["execution_status"] == "confirmed"
    assert result["reconciliation_status"] == "l1_verified"
    assert result["independent_verification"] == "pending"
    assert result["unavailable_source_ids"] == ["provider_b_devnet"]


def test_l2_without_l1_does_not_become_reconciled(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    expected, l1, _ = live
    l2_descriptor = independent_descriptor()
    l2 = from_source(l1, l2_descriptor)
    result = aggregate_reconciliation(
        expected,
        [l2],
        SourceRegistry([l2_descriptor]),
    )
    assert result["reconciliation_status"] == "pending"
    assert result["independent_verification"] == "pending"


def test_adapter_hashes_raw_provider_response_and_normalizes_snapshot(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    _, l1, _ = live
    descriptor = independent_descriptor()

    class Reader:
        def read(self, **_: str) -> TransactionSnapshot:
            return TransactionSnapshot(
                signature=l1["signature"],
                network=l1["network"],
                slot=l1["slot"],
                confirmation_status="finalized",
                transaction_error="none",
                source_account=l1["source_account"],
                destination_account=l1["destination_account"],
                source_account_before="100000000",
                source_account_after="99000000",
                destination_account_before="0",
                destination_account_after="1000000",
                raw_response=b'{"provider":"b","result":"finalized"}',
            )

    source = ObservationSource(
        descriptor,
        Reader(),
        now=lambda: datetime(2026, 7, 23, 21, 0, tzinfo=UTC),
    )
    observation = source.observe(
        signature=l1["signature"],
        source_account=l1["source_account"],
        destination_account=l1["destination_account"],
    )
    assert observation["confirmation_status"] == "finalized"
    assert observation["raw_response_hash"].startswith("sha256:")
    assert list(VALIDATOR.iter_errors(observation)) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_account_after", "100000001"),
        ("destination_account_after", "999999"),
        ("observed_amount_base_units", "999999"),
    ],
)
def test_inconsistent_balance_observation_is_rejected(
    live: tuple[dict, dict, SourceDescriptor],
    field: str,
    value: str,
) -> None:
    _, observation, _ = live
    changed = copy.deepcopy(observation)
    changed[field] = value
    with pytest.raises(ReconciliationInvalid, match="balance"):
        normalize_observation(changed)


def test_impossible_utc_calendar_timestamp_is_rejected(
    live: tuple[dict, dict, SourceDescriptor],
) -> None:
    _, observation, _ = live
    changed = copy.deepcopy(observation)
    changed["queried_at"] = "2026-02-31T21:00:00Z"
    with pytest.raises(ReconciliationInvalid, match="calendar"):
        normalize_observation(changed)
