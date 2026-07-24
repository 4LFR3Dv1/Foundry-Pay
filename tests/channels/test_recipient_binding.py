"""FC-PROTO-003 claim and dual-signature recipient-binding tests."""

from __future__ import annotations

import copy
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "packages" / "channel-protocol" / "python"))

from foundry_channel_protocol.recipient_binding import (  # noqa: E402
    RecipientBindingContext,
    RecipientBindingLedger,
    RecipientBindingValidationError,
    canonical_recipient_binding_payload,
    validate_channel_claim,
    verify_recipient_binding,
)


VECTOR_PATH = (
    ROOT
    / "contracts"
    / "channel"
    / "test-vectors"
    / "positive"
    / "recipient-binding-initial-v1.json"
)


@pytest.fixture()
def vector() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def context(vector: dict[str, Any]) -> RecipientBindingContext:
    return RecipientBindingContext(**vector["context"])


def at(vector: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(vector["now"].replace("Z", "+00:00"))


class ExactVerifier:
    """Synthetic verifier that records the exact byte object passed to both calls."""

    def __init__(self, vector: dict[str, Any]) -> None:
        binding = vector["binding"]
        payload = binding["payload"]
        self.accepted = {
            (
                payload["claim_pubkey"],
                binding["claim_key_signature"],
            ),
            (
                payload["destination_wallet"],
                binding["destination_wallet_signature"],
            ),
        }
        self.expected_payload = bytes.fromhex(vector["expected"]["canonical_payload_hex"])
        self.payloads: list[bytes] = []

    def verify(self, public_key: str, payload: bytes, signature: str) -> bool:
        self.payloads.append(payload)
        return payload == self.expected_payload and (public_key, signature) in self.accepted


class RaisingVerifier:
    def verify(self, public_key: str, payload: bytes, signature: str) -> bool:
        raise RuntimeError("synthetic verifier outage")


def assert_rejected(code: str, operation: object) -> None:
    with pytest.raises(RecipientBindingValidationError) as caught:
        operation()
    assert caught.value.code == code


def set_path(document: dict[str, Any], path: str, value: object) -> None:
    parts = path.split(".")
    current: dict[str, Any] = document
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def refresh_hash(binding: dict[str, Any], vector: dict[str, Any]) -> None:
    payload = canonical_recipient_binding_payload(
        binding,
        context=context(vector),
        claim=vector["claim"],
        now=at(vector),
    )
    import hashlib

    binding["binding_hash"] = f"sha256:{hashlib.sha256(payload).hexdigest()}"


def test_schemas_accept_published_positive_vector(vector: dict[str, Any]) -> None:
    schema_root = ROOT / "contracts" / "channel"
    format_checker = FormatChecker()
    for value_key, schema_name in (
        ("claim", "channel-claim.schema.json"),
        ("binding", "recipient-binding.schema.json"),
    ):
        schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = list(
            Draft202012Validator(schema, format_checker=format_checker).iter_errors(
                vector[value_key]
            )
        )
        assert errors == []


def test_dual_signatures_receive_identical_canonical_bytes(vector: dict[str, Any]) -> None:
    verifier = ExactVerifier(vector)

    result = verify_recipient_binding(
        vector["claim"],
        vector["binding"],
        context=context(vector),
        signature_verifier=verifier,
        now=at(vector),
    )

    assert result.state == "verified"
    assert "activated" not in result.to_dict().values()
    assert result.binding_hash == vector["expected"]["binding_hash"]
    assert verifier.payloads[0] is verifier.payloads[1]
    assert verifier.payloads[0].hex() == vector["expected"]["canonical_payload_hex"]


def test_channel_claim_is_validated_against_authoritative_context(vector: dict[str, Any]) -> None:
    claim = validate_channel_claim(vector["claim"], context=context(vector), now=at(vector))

    assert claim["voucher_hash"] == vector["context"]["voucher_hash"]
    assert claim["claim_pubkey"] == vector["context"]["claim_pubkey"]


@pytest.mark.parametrize("required_field", ["voucher_hash", "mint"])
def test_required_signed_replay_axis_cannot_be_omitted(
    vector: dict[str, Any], required_field: str
) -> None:
    mutated = copy.deepcopy(vector["binding"])
    del mutated["payload"][required_field]

    assert_rejected(
        "missing_field",
        lambda: verify_recipient_binding(
            vector["claim"],
            mutated,
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


def test_replay_axis_negative_vectors_fail_closed(vector: dict[str, Any]) -> None:
    negative_root = ROOT / "contracts" / "channel" / "test-vectors" / "negative"
    for path in sorted(negative_root.glob("recipient-binding-*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(vector["binding"])
        set_path(mutated, case["mutation"]["path"], case["mutation"]["value"])
        assert_rejected(
            case["expected_error"],
            lambda mutated=mutated: verify_recipient_binding(
                vector["claim"],
                mutated,
                context=context(vector),
                signature_verifier=ExactVerifier(vector),
                now=at(vector),
            ),
        )


@pytest.mark.parametrize(
    ("path", "value", "expected_code"),
    [
        (
            "payload.destination_wallet",
            "SysvarRent111111111111111111111111111111111",
            "binding_hash_mismatch",
        ),
        (
            "payload.domain",
            "foundry.channels.voucher",
            "invalid_literal",
        ),
        ("payload.network", "solana:mainnet", "invalid_literal"),
        (
            "payload.program_id",
            "SysvarRent111111111111111111111111111111111",
            "binding_hash_mismatch",
        ),
        ("payload.channel_id", "channel_other", "binding_hash_mismatch"),
        ("payload.epoch", 1, "binding_hash_mismatch"),
        ("payload.binding_mode", "rebind", "invalid_literal"),
        ("payload.expires_at", "2026-08-01T00:05:30Z", "binding_expired"),
    ],
)
def test_binding_mutations_fail_closed(
    vector: dict[str, Any], path: str, value: object, expected_code: str
) -> None:
    mutated = copy.deepcopy(vector["binding"])
    set_path(mutated, path, value)
    assert_rejected(
        expected_code,
        lambda: verify_recipient_binding(
            vector["claim"],
            mutated,
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("program_id", "SysvarRent111111111111111111111111111111111"),
        ("channel_id", "channel_other"),
        ("epoch", 1),
        ("voucher_hash", "sha256:" + "b" * 64),
        ("mint", "SysvarRent111111111111111111111111111111111"),
    ],
)
def test_rehashed_cross_context_binding_still_rejects(
    vector: dict[str, Any], field: str, value: object
) -> None:
    mutated = copy.deepcopy(vector["binding"])
    mutated["payload"][field] = value
    refresh_hash(mutated, vector)

    assert_rejected(
        "context_mismatch",
        lambda: verify_recipient_binding(
            vector["claim"],
            mutated,
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


@pytest.mark.parametrize(
    ("claim_field", "value"),
    [
        ("channel_id", "channel_other"),
        ("epoch", 1),
        ("voucher_hash", "sha256:" + "b" * 64),
        ("claim_pubkey", "SysvarRent111111111111111111111111111111111"),
    ],
)
def test_claim_context_substitution_rejects(
    vector: dict[str, Any], claim_field: str, value: object
) -> None:
    claim = copy.deepcopy(vector["claim"])
    claim[claim_field] = value

    assert_rejected(
        "context_mismatch",
        lambda: verify_recipient_binding(
            claim,
            vector["binding"],
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


@pytest.mark.parametrize(
    "state",
    ["destination_bound", "settlement_ready", "settled", "expired", "revoked", "blocked"],
)
def test_non_bindable_claim_state_rejects(vector: dict[str, Any], state: str) -> None:
    claim = copy.deepcopy(vector["claim"])
    claim["state"] = state

    assert_rejected(
        "claim_not_bindable",
        lambda: validate_channel_claim(claim, context=context(vector), now=at(vector)),
    )


def test_expired_claim_rejects_before_signature_verification(vector: dict[str, Any]) -> None:
    claim = copy.deepcopy(vector["claim"])
    claim["expires_at"] = "2026-08-01T00:05:30Z"

    assert_rejected(
        "claim_expired",
        lambda: verify_recipient_binding(
            claim,
            vector["binding"],
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


@pytest.mark.parametrize(
    ("signature_field", "expected_code"),
    [
        ("claim_key_signature", "invalid_claim_signature"),
        ("destination_wallet_signature", "invalid_destination_signature"),
    ],
)
def test_each_signature_is_independently_required(
    vector: dict[str, Any], signature_field: str, expected_code: str
) -> None:
    binding = copy.deepcopy(vector["binding"])
    binding[signature_field] = "2" * 64

    assert_rejected(
        expected_code,
        lambda: verify_recipient_binding(
            vector["claim"],
            binding,
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


def test_signature_verifier_error_fails_closed(vector: dict[str, Any]) -> None:
    assert_rejected(
        "signature_verifier_failed",
        lambda: verify_recipient_binding(
            vector["claim"],
            vector["binding"],
            context=context(vector),
            signature_verifier=RaisingVerifier(),
            now=at(vector),
        ),
    )


def test_destination_substitution_with_rehashed_payload_still_needs_both_signatures(
    vector: dict[str, Any],
) -> None:
    binding = copy.deepcopy(vector["binding"])
    binding["payload"]["destination_wallet"] = "SysvarRent111111111111111111111111111111111"
    refresh_hash(binding, vector)

    assert_rejected(
        "invalid_claim_signature",
        lambda: verify_recipient_binding(
            vector["claim"],
            binding,
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


def test_ledger_persists_across_restart_and_nonce_is_one_use(
    vector: dict[str, Any], tmp_path: Path
) -> None:
    path = tmp_path / "bindings.sqlite3"
    first = RecipientBindingLedger(path)
    result = first.verify_and_record(
        vector["claim"],
        vector["binding"],
        context=context(vector),
        signature_verifier=ExactVerifier(vector),
        now=at(vector),
    )

    reopened = RecipientBindingLedger(path)
    assert (
        reopened.get(
            channel_id=result.channel_id,
            epoch=result.epoch,
            claim_id=result.claim_id,
        )
        == result
    )
    assert_rejected(
        "binding_already_recorded",
        lambda: reopened.verify_and_record(
            vector["claim"],
            vector["binding"],
            context=context(vector),
            signature_verifier=ExactVerifier(vector),
            now=at(vector),
        ),
    )


def test_concurrent_initial_binding_has_exactly_one_effect(
    vector: dict[str, Any], tmp_path: Path
) -> None:
    path = tmp_path / "concurrent.sqlite3"
    RecipientBindingLedger(path)

    def attempt() -> str:
        try:
            RecipientBindingLedger(path).verify_and_record(
                vector["claim"],
                vector["binding"],
                context=context(vector),
                signature_verifier=ExactVerifier(vector),
                now=at(vector),
            )
        except RecipientBindingValidationError as error:
            return error.code
        return "verified"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))

    assert sorted(outcomes) == ["binding_already_recorded", "verified"]


def test_schema_rejects_rebind_and_unsigned_extension(vector: dict[str, Any]) -> None:
    schema = json.loads(
        (ROOT / "contracts" / "channel" / "recipient-binding.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    rebind = copy.deepcopy(vector["binding"])
    rebind["payload"]["binding_mode"] = "rebind"
    extension = copy.deepcopy(vector["binding"])
    extension["payload"]["cloud_destination"] = "SysvarRent111111111111111111111111111111111"

    assert list(validator.iter_errors(rebind))
    assert list(validator.iter_errors(extension))
