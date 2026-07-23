"""Reproducible FP-FAIL-001 scenario matrix and evidence generator."""

from __future__ import annotations

import copy
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from foundry_external_execution_protocol import sha256_digest

from services.reconciliation import (
    SourceDescriptor,
    SourceRegistry,
    aggregate_reconciliation,
    normalize_observation,
)
from services.reconciliation.backfill import backfill_fp_e2e_001

from .lab import (
    BroadcastOutcomeUnknown,
    BroadcastUnavailable,
    DurableExecutionLab,
    FailureLabInvalid,
    InjectedCrash,
    SimulatedChain,
)

NOW = datetime(2026, 7, 23, 22, 0, tzinfo=UTC)
MESSAGE_HASH = "sha256:" + "a" * 64
SIGNED_TRANSACTION_HASH = "sha256:" + "b" * 64
SIGNATURE = "failure-lab-signature-" + "c" * 64


def _new_execution(directory: Path, scenario: str) -> tuple[DurableExecutionLab, SimulatedChain]:
    lab = DurableExecutionLab(directory / f"{scenario}.sqlite3")
    lab.register(
        execution_request_id=f"exec_{scenario}",
        obligation_id=f"obl_{scenario}",
        message_hash=MESSAGE_HASH,
        blockhash_valid_until=NOW + timedelta(minutes=5),
        now=NOW,
    )
    return lab, SimulatedChain()


def _sign(lab: DurableExecutionLab, scenario: str) -> None:
    lab.persist_signature(
        f"exec_{scenario}",
        signature=SIGNATURE,
        signed_transaction_hash=SIGNED_TRANSACTION_HASH,
        now=NOW + timedelta(seconds=1),
    )


def _evidence(
    lab: DurableExecutionLab,
    chain: SimulatedChain,
    scenario: str,
) -> dict[str, Any]:
    return lab.evidence(
        f"exec_{scenario}",
        scenario=scenario,
        economic_effect_count=chain.effect_count(f"obl_{scenario}"),
    )


def run_failure_matrix(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Execute all deterministic failures in isolated durable journals."""

    results: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="fp-fail-001-") as temporary:
        root = Path(temporary)

        scenario = "lost_response_after_broadcast"
        lab, chain = _new_execution(root, scenario)
        _sign(lab, scenario)
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=2),
                mode="accepted_response_lost",
            )
        except BroadcastOutcomeUnknown:
            pass
        restarted = DurableExecutionLab(lab.database)
        recovery = restarted.recover(
            f"exec_{scenario}",
            chain,
            now=NOW + timedelta(seconds=3),
        )
        results[scenario] = {
            **_evidence(restarted, chain, scenario),
            "recovery_result": recovery,
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "restart_before_signature_persistence"
        lab, chain = _new_execution(root, scenario)
        try:
            lab.persist_signature(
                f"exec_{scenario}",
                signature=SIGNATURE,
                signed_transaction_hash=SIGNED_TRANSACTION_HASH,
                now=NOW + timedelta(seconds=1),
                fault="before_signature_persist",
            )
        except InjectedCrash:
            pass
        restarted = DurableExecutionLab(lab.database)
        results[scenario] = {
            **_evidence(restarted, chain, scenario),
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "restart_after_signature_persistence"
        lab, chain = _new_execution(root, scenario)
        _sign(lab, scenario)
        restarted = DurableExecutionLab(lab.database)
        results[scenario] = {
            **_evidence(restarted, chain, scenario),
            "persisted_signature": restarted.status(f"exec_{scenario}")["signature"],
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "rpc_unavailable"
        lab, chain = _new_execution(root, scenario)
        _sign(lab, scenario)
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=2),
                mode="unknown_without_effect",
            )
        except BroadcastOutcomeUnknown:
            pass
        chain.observation_mode = "unavailable"
        recovery = lab.recover(
            f"exec_{scenario}",
            chain,
            now=NOW + timedelta(seconds=3),
        )
        results[scenario] = {
            **_evidence(lab, chain, scenario),
            "recovery_result": recovery,
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "broadcast_outcome_unknown"
        lab, chain = _new_execution(root, scenario)
        _sign(lab, scenario)
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=2),
                mode="unknown_without_effect",
            )
        except BroadcastOutcomeUnknown:
            pass
        chain.observation_mode = "unknown"
        recovery = lab.recover(
            f"exec_{scenario}",
            chain,
            now=NOW + timedelta(seconds=3),
        )
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=4),
            )
        except FailureLabInvalid:
            retry_rejected = True
        else:
            retry_rejected = False
        results[scenario] = {
            **_evidence(lab, chain, scenario),
            "automatic_retry_rejected": retry_rejected,
            "recovery_result": recovery,
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "blockhash_expired"
        lab = DurableExecutionLab(root / f"{scenario}.sqlite3")
        chain = SimulatedChain()
        lab.register(
            execution_request_id=f"exec_{scenario}",
            obligation_id=f"obl_{scenario}",
            message_hash=MESSAGE_HASH,
            blockhash_valid_until=NOW + timedelta(seconds=1),
            now=NOW,
        )
        _sign(lab, scenario)
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=2),
            )
        except FailureLabInvalid:
            pass
        results[scenario] = {
            **_evidence(lab, chain, scenario),
            "new_prepare_required": True,
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "known_rpc_rejection"
        lab, chain = _new_execution(root, scenario)
        _sign(lab, scenario)
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=2),
                mode="unavailable_before_acceptance",
            )
        except BroadcastUnavailable:
            pass
        results[scenario] = {
            **_evidence(lab, chain, scenario),
            "provider_broadcast_calls": chain.calls,
        }

        scenario = "recovery_without_second_broadcast"
        lab, chain = _new_execution(root, scenario)
        _sign(lab, scenario)
        try:
            lab.execute(
                f"exec_{scenario}",
                chain,
                now=NOW + timedelta(seconds=2),
                mode="accepted_response_lost",
            )
        except BroadcastOutcomeUnknown:
            pass
        first = lab.recover(
            f"exec_{scenario}",
            chain,
            now=NOW + timedelta(seconds=3),
        )
        second = lab.recover(
            f"exec_{scenario}",
            chain,
            now=NOW + timedelta(seconds=4),
        )
        results[scenario] = {
            **_evidence(lab, chain, scenario),
            "first_recovery": first,
            "second_recovery": second,
            "provider_broadcast_calls": chain.calls,
        }

    results["reconciliation_l1_l2_divergence"] = _divergence(repo_root)
    return results


def _divergence(repo_root: Path) -> dict[str, Any]:
    proof = repo_root / "evidence" / "runs" / "FP-E2E-001" / "live-proof.json"
    expected, l1, l1_descriptor = backfill_fp_e2e_001(proof)
    l2_path = repo_root / "evidence" / "runs" / "FP-REC-001" / "l2-observation.json"
    l2 = json.loads(l2_path.read_text(encoding="utf-8"))
    divergent = copy.deepcopy(l2)
    divergent["source_account_after"] = "98000000"
    divergent["destination_account_after"] = "2000000"
    divergent["observed_amount_base_units"] = "2000000"
    divergent = normalize_observation(divergent)
    l2_descriptor = SourceDescriptor(
        **{
            field: divergent[field]
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
    aggregate = aggregate_reconciliation(
        expected,
        [l1, divergent],
        SourceRegistry([l1_descriptor, l2_descriptor]),
    )
    return {
        "type": "failure_scenario_evidence",
        "protocol_version": "1.0.0",
        "scenario": "reconciliation_l1_l2_divergence",
        "execution_request_id": expected["execution_request_id"],
        "obligation_id": expected["obligation_id"],
        "final_state": aggregate["reconciliation_status"],
        "execution_status_preserved": aggregate["execution_status"],
        "broadcast_count": 1,
        "economic_effect_count": 1,
        "may_rematerialize": False,
        "aggregate": aggregate,
    }


def write_failure_evidence(
    repo_root: Path,
    output_directory: Path,
    *,
    implementation_commit: str,
) -> None:
    results = run_failure_matrix(repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, str]] = []
    for scenario, report in sorted(results.items()):
        name = f"{scenario}.json"
        payload = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        (output_directory / name).write_bytes(payload)
        artifacts.append({"path": name, "sha256": sha256_digest(payload)})
    manifest = {
        "work_item": "FP-FAIL-001",
        "implementation_commit": implementation_commit,
        "scenario_count": len(results),
        "all_broadcast_counts_at_most_one": all(
            report["broadcast_count"] <= 1 for report in results.values()
        ),
        "all_unknown_outcomes_non_rematerializable": all(
            not report["may_rematerialize"]
            for report in results.values()
            if report["final_state"] == "needs_recovery"
        ),
        "artifacts": artifacts,
    }
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    (output_directory / "manifest.json").write_bytes(payload)
