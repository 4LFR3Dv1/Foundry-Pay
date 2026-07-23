from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from foundry_external_execution_protocol import sha256_digest

from services.failure_lab import (
    BroadcastOutcomeUnknown,
    DurableExecutionLab,
    FailureLabInvalid,
    InjectedCrash,
    SimulatedChain,
    run_failure_matrix,
    write_failure_evidence,
)

ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 7, 23, 22, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def matrix() -> dict[str, dict]:
    return run_failure_matrix(ROOT)


def test_matrix_contains_every_required_failure(matrix: dict[str, dict]) -> None:
    assert set(matrix) == {
        "lost_response_after_broadcast",
        "restart_before_signature_persistence",
        "restart_after_signature_persistence",
        "rpc_unavailable",
        "broadcast_outcome_unknown",
        "blockhash_expired",
        "known_rpc_rejection",
        "recovery_without_second_broadcast",
        "reconciliation_l1_l2_divergence",
    }


def test_lost_response_recovers_persisted_effect_once(matrix: dict[str, dict]) -> None:
    report = matrix["lost_response_after_broadcast"]
    assert report["final_state"] == "confirmed"
    assert report["signature_persisted"] is True
    assert report["broadcast_count"] == 1
    assert report["provider_broadcast_calls"] == 1
    assert report["economic_effect_count"] == 1
    assert report["recovery_result"]["outcome"] == "confirmed"
    assert report["may_rematerialize"] is False


def test_restart_before_signature_proves_no_broadcast(matrix: dict[str, dict]) -> None:
    report = matrix["restart_before_signature_persistence"]
    assert report["final_state"] == "authorized"
    assert report["signature_persisted"] is False
    assert report["broadcast_count"] == 0
    assert report["provider_broadcast_calls"] == 0
    assert report["economic_effect_count"] == 0


def test_restart_after_signature_preserves_exact_signature(matrix: dict[str, dict]) -> None:
    report = matrix["restart_after_signature_persistence"]
    assert report["final_state"] == "signed"
    assert report["signature_persisted"] is True
    assert report["persisted_signature"].startswith("failure-lab-signature-")
    assert report["broadcast_count"] == 0
    event_types = [event["event_type"] for event in report["events"]]
    assert event_types == ["execution_registered", "signature_persisted"]


def test_rpc_unavailability_stays_pending_without_retry(matrix: dict[str, dict]) -> None:
    report = matrix["rpc_unavailable"]
    assert report["final_state"] == "needs_recovery"
    assert report["recovery_result"]["outcome"] == "needs_recovery"
    assert report["broadcast_count"] == 1
    assert report["provider_broadcast_calls"] == 1
    assert report["economic_effect_count"] == 0
    assert report["may_rematerialize"] is False


def test_unknown_broadcast_rejects_automatic_retry(matrix: dict[str, dict]) -> None:
    report = matrix["broadcast_outcome_unknown"]
    assert report["final_state"] == "needs_recovery"
    assert report["automatic_retry_rejected"] is True
    assert report["provider_broadcast_calls"] == 1
    assert report["broadcast_count"] == 1
    assert report["may_rematerialize"] is False


def test_expired_blockhash_requires_new_prepare_before_any_broadcast(
    matrix: dict[str, dict],
) -> None:
    report = matrix["blockhash_expired"]
    assert report["final_state"] == "expired_requires_new_prepare"
    assert report["new_prepare_required"] is True
    assert report["broadcast_count"] == 0
    assert report["provider_broadcast_calls"] == 0
    assert report["may_rematerialize"] is True


def test_known_rpc_rejection_is_distinct_from_unknown(matrix: dict[str, dict]) -> None:
    report = matrix["known_rpc_rejection"]
    assert report["final_state"] == "broadcast_failed_known"
    assert report["provider_broadcast_calls"] == 1
    assert report["economic_effect_count"] == 0
    assert report["may_rematerialize"] is True


def test_repeated_recovery_never_broadcasts_again(matrix: dict[str, dict]) -> None:
    report = matrix["recovery_without_second_broadcast"]
    assert report["first_recovery"]["outcome"] == "confirmed"
    assert report["second_recovery"]["outcome"] == "confirmed"
    assert report["broadcast_count"] == 1
    assert report["provider_broadcast_calls"] == 1
    assert report["economic_effect_count"] == 1


def test_l1_l2_divergence_opens_dispute_without_rewriting_execution(
    matrix: dict[str, dict],
) -> None:
    report = matrix["reconciliation_l1_l2_divergence"]
    assert report["final_state"] == "reconciliation_disputed"
    assert report["execution_status_preserved"] == "confirmed"
    assert report["aggregate"]["independent_verification"] == "disputed"
    assert report["aggregate"]["consensus"] == "disputed"
    assert report["broadcast_count"] == 1
    assert report["economic_effect_count"] == 1
    assert report["may_rematerialize"] is False


def test_signature_event_always_precedes_broadcast_intent(matrix: dict[str, dict]) -> None:
    for report in matrix.values():
        events = report.get("events", [])
        event_types = [event["event_type"] for event in events]
        if "broadcast_intent_persisted" in event_types:
            assert event_types.index("signature_persisted") < event_types.index(
                "broadcast_intent_persisted"
            )


def test_crash_after_broadcast_intent_is_conservatively_unknown(tmp_path: Path) -> None:
    lab = DurableExecutionLab(tmp_path / "journal.sqlite3")
    chain = SimulatedChain()
    lab.register(
        execution_request_id="exec_crash",
        obligation_id="obl_crash",
        message_hash="sha256:" + "a" * 64,
        blockhash_valid_until=NOW + timedelta(minutes=5),
        now=NOW,
    )
    lab.persist_signature(
        "exec_crash",
        signature="signature-" + "s" * 64,
        signed_transaction_hash="sha256:" + "b" * 64,
        now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(InjectedCrash):
        lab.execute(
            "exec_crash",
            chain,
            now=NOW + timedelta(seconds=2),
            fault="after_broadcast_intent_before_call",
        )

    restarted = DurableExecutionLab(lab.database)
    assert restarted.status("exec_crash")["state"] == "needs_recovery"
    assert restarted.status("exec_crash")["broadcast_count"] == 1
    assert chain.calls == 0
    with pytest.raises(FailureLabInvalid, match="forbids automatic broadcast"):
        restarted.execute(
            "exec_crash",
            chain,
            now=NOW + timedelta(minutes=6),
        )
    assert chain.calls == 0


def test_unknown_outcome_remains_blocked_after_blockhash_expiry(tmp_path: Path) -> None:
    lab = DurableExecutionLab(tmp_path / "journal.sqlite3")
    chain = SimulatedChain()
    lab.register(
        execution_request_id="exec_unknown",
        obligation_id="obl_unknown",
        message_hash="sha256:" + "a" * 64,
        blockhash_valid_until=NOW + timedelta(seconds=3),
        now=NOW,
    )
    lab.persist_signature(
        "exec_unknown",
        signature="signature-" + "s" * 64,
        signed_transaction_hash="sha256:" + "b" * 64,
        now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(BroadcastOutcomeUnknown):
        lab.execute(
            "exec_unknown",
            chain,
            now=NOW + timedelta(seconds=2),
            mode="unknown_without_effect",
        )
    chain.observation_mode = "unknown"
    result = lab.recover(
        "exec_unknown",
        chain,
        now=NOW + timedelta(minutes=1),
    )
    assert result["outcome"] == "needs_recovery"
    report = lab.evidence(
        "exec_unknown",
        scenario="unknown_after_expiry",
        economic_effect_count=0,
    )
    assert report["may_rematerialize"] is False


def test_event_chain_tampering_is_detected(tmp_path: Path) -> None:
    lab = DurableExecutionLab(tmp_path / "journal.sqlite3")
    chain = SimulatedChain()
    lab.register(
        execution_request_id="exec_tamper",
        obligation_id="obl_tamper",
        message_hash="sha256:" + "a" * 64,
        blockhash_valid_until=NOW + timedelta(minutes=5),
        now=NOW,
    )
    with sqlite3.connect(lab.database) as connection:
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE execution_request_id = ?",
            (json.dumps({"message_hash": "tampered"}), "exec_tamper"),
        )
    with pytest.raises(FailureLabInvalid, match="hash mismatch"):
        lab.evidence(
            "exec_tamper",
            scenario="tamper",
            economic_effect_count=chain.effect_count("obl_tamper"),
        )


def test_obligation_cannot_be_rematerialized_while_registered(tmp_path: Path) -> None:
    lab = DurableExecutionLab(tmp_path / "journal.sqlite3")
    lab.register(
        execution_request_id="exec_first",
        obligation_id="obl_same",
        message_hash="sha256:" + "a" * 64,
        blockhash_valid_until=NOW + timedelta(minutes=5),
        now=NOW,
    )
    with pytest.raises(FailureLabInvalid, match="already has execution state"):
        lab.register(
            execution_request_id="exec_second",
            obligation_id="obl_same",
            message_hash="sha256:" + "b" * 64,
            blockhash_valid_until=NOW + timedelta(minutes=5),
            now=NOW,
        )


def test_generated_evidence_manifest_binds_every_scenario(tmp_path: Path) -> None:
    write_failure_evidence(
        ROOT,
        tmp_path,
        implementation_commit="f" * 40,
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["scenario_count"] == 9
    assert manifest["all_broadcast_counts_at_most_one"] is True
    assert manifest["all_unknown_outcomes_non_rematerializable"] is True
    assert len(manifest["artifacts"]) == 9
    for artifact in manifest["artifacts"]:
        assert (tmp_path / artifact["path"]).is_file()
        assert artifact["sha256"].startswith("sha256:")


def test_committed_evidence_manifest_hashes_every_report() -> None:
    evidence = ROOT / "evidence" / "runs" / "FP-FAIL-001"
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["scenario_count"] == 9
    assert manifest["all_broadcast_counts_at_most_one"] is True
    assert manifest["all_unknown_outcomes_non_rematerializable"] is True
    assert len(manifest["implementation_commit"]) == 40
    for artifact in manifest["artifacts"]:
        payload = (evidence / artifact["path"]).read_bytes()
        assert sha256_digest(payload) == artifact["sha256"]
