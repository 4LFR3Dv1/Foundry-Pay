from __future__ import annotations

import os
from pathlib import Path

import pytest

from services.process_chaos import run_process_matrix

ROOT = Path(__file__).parents[2]
SOLANA_AGENT = Path(os.environ.get("SOLANA_AGENT_ROOT", ROOT.parent / "Solana-Agent")).resolve()


@pytest.fixture(scope="module")
def matrix() -> dict[str, dict]:
    if not (SOLANA_AGENT / "gateway" / "chaos_scenario.py").is_file():
        pytest.skip("SA-CHAOS-001 checkout is unavailable")
    return run_process_matrix(
        foundry_root=ROOT,
        solana_agent_root=SOLANA_AGENT,
    )


def test_matrix_contains_nine_cross_boundary_scenarios(
    matrix: dict[str, dict],
) -> None:
    assert set(matrix) == {
        "kill_before_broadcast",
        "kill_after_broadcast_intent",
        "kill_during_send_transaction",
        "response_lost_after_acceptance",
        "definitive_rejection",
        "not_found_after_expiry",
        "replay_after_restart",
        "concurrent_gateways",
        "source_unavailable_then_converged",
    }


def test_kill_before_claim_proves_zero_broadcasts(matrix: dict[str, dict]) -> None:
    report = matrix["kill_before_broadcast"]
    assert report["proxy_send_transaction"]["requests_received"] == 0
    assert report["proxy_send_transaction"]["upstream_requests_forwarded"] == 0
    assert report["kill_sentinel"]["point"] == ("after_execution_validated_before_claim")
    assert report["gateway_responses"][0] is None
    assert report["gateway_responses"][1]["result"]["state"] == "prepared"


def test_kill_after_intent_is_unknown_without_rpc_call(
    matrix: dict[str, dict],
) -> None:
    report = matrix["kill_after_broadcast_intent"]
    assert report["proxy_send_transaction"]["requests_received"] == 0
    assert report["kill_sentinel"]["point"] == ("after_signature_and_broadcast_intent_persisted")
    assert report["recovery_response"]["result"]["outcome"] == "needs_recovery"
    assert report["recovery_response"]["result"]["may_rematerialize"] is False


@pytest.mark.parametrize(
    "scenario",
    [
        "kill_during_send_transaction",
        "response_lost_after_acceptance",
    ],
)
def test_accepted_send_recovers_confirmed_without_rebroadcast(
    matrix: dict[str, dict],
    scenario: str,
) -> None:
    report = matrix[scenario]
    metrics = report["proxy_send_transaction"]
    assert metrics["requests_received"] == 1
    assert metrics["upstream_requests_forwarded"] == 1
    assert metrics["upstream_responses_received"] == 1
    assert report["recovery_response"]["result"]["outcome"] == ("recovered_confirmed")
    assert report["upstream_metrics"]["accepted_transactions"][0]["accepted_count"] == 1


def test_definitive_rejection_is_not_unknown(matrix: dict[str, dict]) -> None:
    report = matrix["definitive_rejection"]
    execute, evidence = report["gateway_responses"]
    assert execute["error"]["code"] == "definitive_rejection"
    assert evidence["result"]["execution"]["state"] == "failed"
    assert report["proxy_send_transaction"]["requests_received"] == 1
    assert report["proxy_send_transaction"]["upstream_requests_forwarded"] == 0
    assert report["upstream_metrics"]["accepted_transactions"] == []


def test_not_found_after_expiry_still_requires_reconciliation(
    matrix: dict[str, dict],
) -> None:
    report = matrix["not_found_after_expiry"]
    recovery = report["recovery_response"]["result"]
    assert recovery["outcome"] == "not_found_after_expiry_needs_reconciliation"
    assert recovery["state"] == "needs_recovery"
    assert recovery["may_rematerialize"] is False
    assert report["proxy_send_transaction"]["upstream_requests_forwarded"] == 0


def test_replay_after_restart_reuses_response_and_never_sends_again(
    matrix: dict[str, dict],
) -> None:
    report = matrix["replay_after_restart"]
    first, replay = report["gateway_responses"]
    assert first["error"]["code"] == "needs_recovery"
    assert replay["error"]["code"] == "needs_recovery"
    assert replay["replayed"] is True
    assert report["proxy_send_transaction"]["requests_received"] == 1
    assert report["upstream_metrics"]["accepted_transactions"][0]["accepted_count"] == 1


def test_two_gateway_processes_produce_one_claim_and_one_send(
    matrix: dict[str, dict],
) -> None:
    report = matrix["concurrent_gateways"]
    responses = report["gateway_responses"]
    assert sum(response["ok"] is True for response in responses) == 1
    assert (
        sum(
            response.get("error", {}).get("code")
            in {
                "needs_recovery",
                "execution_already_started",
            }
            for response in responses
        )
        == 1
    )
    assert report["proxy_send_transaction"]["requests_received"] == 1
    assert report["upstream_metrics"]["accepted_transactions"][0]["accepted_count"] == 1


def test_unavailable_l2_is_pending_then_converges_with_history(
    matrix: dict[str, dict],
) -> None:
    report = matrix["source_unavailable_then_converged"]
    assert report["initial_reconciliation_status"] == "l1_verified"
    assert report["initial_independent_verification"] == "pending"
    assert report["final_reconciliation_status"] == "l1_verified"
    assert report["final_independent_verification"] == "l2_verified"
    assert report["history_preserved"] is True
    assert [item["event"] for item in report["history"]] == [
        "l2_unavailable",
        "l2_converged",
    ]


def test_no_scenario_persists_private_material_or_second_send(
    matrix: dict[str, dict],
) -> None:
    for report in matrix.values():
        assert report["private_material_persisted"] is False
        metrics = report.get("proxy_send_transaction")
        if metrics is not None:
            assert metrics["requests_received"] <= 1
