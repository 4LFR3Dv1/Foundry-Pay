from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.reconciliation import (
    ObservationSource,
    ReconciliationInvalid,
    SolanaRpcSnapshotReader,
    SourceDescriptor,
    endpoint_identity_hash,
)
from services.reconciliation.backfill import backfill_fp_e2e_001

ROOT = Path(__file__).parents[2]
PROOF = ROOT / "evidence" / "runs" / "FP-E2E-001" / "live-proof.json"


def _responses(*, status: str = "finalized", error: object = None) -> dict[str, bytes]:
    _, l1, _ = backfill_fp_e2e_001(PROOF)
    accounts = [
        {"pubkey": "11111111111111111111111111111111"},
        {"pubkey": l1["source_account"]},
        {"pubkey": l1["destination_account"]},
    ]
    transaction = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "slot": l1["slot"],
            "transaction": {"message": {"accountKeys": accounts}},
            "meta": {
                "err": error,
                "preTokenBalances": [
                    {"accountIndex": 1, "uiTokenAmount": {"amount": "100000000"}},
                    {"accountIndex": 2, "uiTokenAmount": {"amount": "0"}},
                ],
                "postTokenBalances": [
                    {"accountIndex": 1, "uiTokenAmount": {"amount": "99000000"}},
                    {"accountIndex": 2, "uiTokenAmount": {"amount": "1000000"}},
                ],
            },
        },
    }
    statuses = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "value": [
                {
                    "slot": l1["slot"],
                    "err": error,
                    "confirmationStatus": status,
                }
            ]
        },
    }
    return {
        "getTransaction": json.dumps(transaction, separators=(",", ":")).encode(),
        "getSignatureStatuses": json.dumps(statuses, separators=(",", ":")).encode(),
    }


def test_rpc_reader_builds_snapshot_from_independent_wire_responses() -> None:
    _, l1, _ = backfill_fp_e2e_001(PROOF)
    responses = _responses()
    requested_methods: list[str] = []

    def transport(endpoint: str, payload: bytes) -> bytes:
        assert endpoint == "https://credential-bearing.example/v2/secret"
        method = json.loads(payload)["method"]
        requested_methods.append(method)
        return responses[method]

    descriptor = SourceDescriptor(
        source_id="alchemy_devnet",
        source_class="L2",
        source_kind="rpc",
        provider_id="alchemy",
        trust_domain_id="alchemy_infrastructure",
        endpoint_identity_hash=endpoint_identity_hash("https://solana-devnet.g.alchemy.com/v2"),
        parser_id="solana_json_rpc_reader_v1",
    )
    source = ObservationSource(
        descriptor,
        SolanaRpcSnapshotReader(
            "https://credential-bearing.example/v2/secret",
            transport=transport,
        ),
    )
    observation = source.observe(
        signature=l1["signature"],
        source_account=l1["source_account"],
        destination_account=l1["destination_account"],
    )

    assert requested_methods == ["getTransaction", "getSignatureStatuses"]
    assert observation["source_class"] == "L2"
    assert observation["confirmation_status"] == "finalized"
    assert observation["observed_amount_base_units"] == "1000000"
    assert observation["raw_response_hash"].startswith("sha256:")


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda responses: responses.__setitem__(
                "getTransaction",
                b'{"jsonrpc":"2.0","id":1,"result":null}',
            ),
            "no transaction",
        ),
        (
            lambda responses: responses.__setitem__(
                "getSignatureStatuses",
                b'{"jsonrpc":"2.0","id":2,"result":{"value":[null]}}',
            ),
            "unavailable",
        ),
        (
            lambda responses: responses.__setitem__(
                "getTransaction",
                b'{"jsonrpc":"2.0","id":1,"error":{"code":-1}}',
            ),
            "RPC error",
        ),
    ],
)
def test_rpc_reader_fails_closed_on_incomplete_provider_data(
    mutator,
    message: str,
) -> None:
    _, l1, _ = backfill_fp_e2e_001(PROOF)
    responses = _responses()
    mutator(responses)

    def transport(_: str, payload: bytes) -> bytes:
        return responses[json.loads(payload)["method"]]

    reader = SolanaRpcSnapshotReader("https://provider.example", transport=transport)
    with pytest.raises(ReconciliationInvalid, match=message):
        reader.read(
            signature=l1["signature"],
            source_account=l1["source_account"],
            destination_account=l1["destination_account"],
        )
