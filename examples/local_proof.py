"""Run a deterministic governed-execution proof without a wallet or RPC."""

from __future__ import annotations

import copy
import gc
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from foundry_external_execution_protocol import (
    AuthorizationReplay,
    FakeAuthorizationAuthority,
    FakeExternalExecutor,
    ResponseLost,
    economic_plan_hash,
)


ROOT = Path(__file__).parents[1]
VECTOR_PATH = (
    ROOT
    / "packages"
    / "external-execution-protocol"
    / "conformance"
    / "vectors"
    / "protocol-v1.json"
)
NOW = datetime(2026, 7, 23, 17, 30, tzinfo=UTC)
SIGNER = "11111111111111111111111111111111"
AUTHORIZATION_KEY = b"foundry-local-proof-authorization-key-v1"


def run_local_proof(database: Path) -> dict[str, object]:
    vector = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    plan = copy.deepcopy(vector["economic_plan"])
    plan_hash = economic_plan_hash(plan)
    request = {
        "type": "external_execution_request",
        "protocol_version": "1.0.0",
        "execution_request_id": "exec_quickstart_001",
        "idempotency_key": "idem_quickstart_001",
        "economic_plan": plan,
        "economic_plan_hash": plan_hash,
        "economic_approval": {
            "approval_id": "approval_quickstart_001",
            "economic_plan_hash": plan_hash,
            "approved_by": "local_operator",
            "issued_at": "2026-07-23T17:00:00Z",
            "expires_at": "2026-07-23T18:00:00Z",
        },
    }
    simulation = {
        "rpc_provider_id": "deterministic-local-rpc",
        "genesis_hash": "g" * 32,
        "slot": 123,
        "commitment_level": "confirmed",
        "recent_blockhash": "b" * 32,
        "last_valid_block_height": 456,
        "simulated_at": "2026-07-23T17:29:00Z",
        "valid_until": "2026-07-23T17:55:00Z",
        "logs_hash": "sha256:" + "a" * 64,
        "pre_balances_hash": "sha256:" + "b" * 64,
        "post_balances_hash": "sha256:" + "c" * 64,
        "units_consumed": 1200,
        "fee_lamports": 5000,
        "success": True,
    }

    authority = FakeAuthorizationAuthority(AUTHORIZATION_KEY)
    executor = FakeExternalExecutor(database, authorization_authority=authority)
    prepared = executor.prepare(
        request,
        simulation=simulation,
        signer=SIGNER,
        constraints={
            "max_fee_lamports": 50_000,
            "allowed_programs": [SIGNER],
        },
        expires_at="2026-07-23T17:50:00Z",
        now=NOW,
    )
    authorization = authority.issue(
        prepared,
        authorization_id="auth_quickstart_001",
        issued_at="2026-07-23T17:31:00Z",
        expires_at="2026-07-23T17:40:00Z",
    )

    response_lost = False
    try:
        executor.authorize_and_execute(
            authorization,
            now=datetime(2026, 7, 23, 17, 32, tzinfo=UTC),
            fault="after_commit_before_response",
        )
    except ResponseLost:
        response_lost = True

    recovery = executor.recover(
        "exec_quickstart_001",
        observed_at=datetime(2026, 7, 23, 17, 33, tzinfo=UTC),
    )
    receipt = executor.receipt("exec_quickstart_001")

    replay_blocked = False
    try:
        executor.authorize_and_execute(
            authorization,
            now=datetime(2026, 7, 23, 17, 34, tzinfo=UTC),
        )
    except AuthorizationReplay:
        replay_blocked = True

    result: dict[str, object] = {
        "execution_request_id": "exec_quickstart_001",
        "prepared_message_hash": prepared["prepared_message_hash"],
        "execution_commitment_hash": prepared["execution_commitment_hash"],
        "response_lost_after_commit": response_lost,
        "recovery_outcome": recovery["outcome"],
        "may_rematerialize": recovery["may_rematerialize"],
        "receipt_hash": receipt["receipt_hash"] if receipt else None,
        "replay_blocked": replay_blocked,
        "economic_effect_count": executor.effect_count("obl_demo_001"),
    }
    expected = {
        "response_lost_after_commit": True,
        "recovery_outcome": "confirmed",
        "may_rematerialize": False,
        "replay_blocked": True,
        "economic_effect_count": 1,
    }
    for field, value in expected.items():
        if result[field] != value:
            raise RuntimeError(f"local proof failed: {field}={result[field]!r}")
    return result


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="foundry-pay-") as directory:
        result = run_local_proof(Path(directory) / "executor.sqlite3")
        # sqlite3 context managers commit or roll back but do not close their
        # connection objects. Force finalization before Windows removes the
        # temporary database.
        gc.collect()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
