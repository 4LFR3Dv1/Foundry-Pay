"""Prove rejected mutations have no economic or authority-advancing effect."""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import rfc8785


ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(ROOT / "packages/channel-protocol/python"))

from foundry_channel_protocol import (  # noqa: E402
    ReferenceVoucherLedger,
    VoucherContext,
    VoucherValidationError,
)
from foundry_channel_protocol.recipient_binding import (  # noqa: E402
    RecipientBindingContext,
    RecipientBindingLedger,
    RecipientBindingValidationError,
)


NOW = datetime(2026, 8, 1, 0, 6, tzinfo=timezone.utc)


class NeverVerifyVoucher:
    def __call__(self, public_key: str, payload: bytes, signature: str) -> bool:
        del public_key, payload, signature
        return False


class NeverVerifyBinding:
    def verify(self, public_key: str, payload: bytes, signature: str) -> bool:
        del public_key, payload, signature
        return False


def load_voucher_vector() -> dict[str, Any]:
    return json.loads(
        (ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json").read_text(
            encoding="utf-8"
        )
    )


def load_binding_vector() -> dict[str, Any]:
    return json.loads(
        (
            ROOT / "contracts/channel/test-vectors/positive/recipient-binding-initial-v1.json"
        ).read_text(encoding="utf-8")
    )


def voucher_context(vector: dict[str, Any]) -> VoucherContext:
    constants = vector["constants"]
    previous = vector["vouchers"][1]
    return VoucherContext(
        environment=constants["environment"],
        network=constants["network"],
        genesis_hash=constants["genesis_hash"],
        program_id=constants["program_id"],
        channel_id=constants["channel_id"],
        channel_account=constants["channel_account"],
        epoch=0,
        sender=constants["sender"],
        recipient_claim_pubkey=constants["claim_pubkey"],
        mint=constants["mint"],
        funded_total_base_units=100_000_000,
        refunded_total_base_units=0,
        policy_limit_base_units=100_000_000,
        channel_expires_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        latest_activated_sequence=2,
        latest_activated_total_base_units=25_000_000,
        latest_activated_voucher_hash=previous["voucher_hash"],
    )


def binding_context(vector: dict[str, Any]) -> RecipientBindingContext:
    return RecipientBindingContext(**vector["context"])


def test_voucher_rejection_is_audit_only_and_never_advances_authority(
    tmp_path: Path,
) -> None:
    vector = load_voucher_vector()
    voucher = copy.deepcopy(vector["vouchers"][2])
    voucher["payload"]["channel_id"] = "channel_structurally_valid_other"
    voucher["voucher_hash"] = (
        "sha256:" + hashlib.sha256(rfc8785.dumps(voucher["payload"])).hexdigest()
    )
    database = tmp_path / "voucher.sqlite"
    ledger = ReferenceVoucherLedger(database)
    ledger.record_issued("attack_cross_channel", voucher, observed_at=NOW)

    with pytest.raises(VoucherValidationError) as caught:
        ledger.verify_issued(
            "attack_cross_channel",
            context=voucher_context(vector),
            now=NOW,
            signature_verifier=NeverVerifyVoucher(),
        )
    assert caught.value.code == "channel_mismatch"

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT state, voucher_hash, domain_key, channel_id, epoch, sequence,
                   cumulative_total
            FROM voucher_submissions
            WHERE submission_id = 'attack_cross_channel'
            """
        ).fetchone()
        transitions = dict(
            connection.execute(
                """
                SELECT state, COUNT(*)
                FROM voucher_events
                WHERE submission_id = 'attack_cross_channel'
                GROUP BY state
                """
            ).fetchall()
        )

    assert row == ("rejected", None, None, None, None, None, None)
    assert transitions == {"issued": 1, "rejected": 1}
    assert transitions.get("verified", 0) == 0
    assert transitions.get("activation_requested", 0) == 0


def test_binding_rejection_does_not_consume_nonce_or_create_record(
    tmp_path: Path,
) -> None:
    vector = load_binding_vector()
    binding = copy.deepcopy(vector["binding"])
    binding["payload"]["destination_wallet"] = "SysvarRent111111111111111111111111111111111"
    database = tmp_path / "binding.sqlite"
    ledger = RecipientBindingLedger(database)

    with pytest.raises(RecipientBindingValidationError) as caught:
        ledger.verify_and_record(
            vector["claim"],
            binding,
            context=binding_context(vector),
            signature_verifier=NeverVerifyBinding(),
            now=NOW,
        )
    assert caught.value.code == "binding_hash_mismatch"

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM recipient_bindings").fetchone()[0]

    assert count == 0
    assert ledger.get(context=binding_context(vector)) is None
