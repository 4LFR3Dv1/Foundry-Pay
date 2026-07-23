from __future__ import annotations

import base64
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

import services.signer.boundary as signer_module
from services.authorization import authorization_signing_payload
from services.signer import (
    ExactMessageSigner,
    SignerExpired,
    SignerInvalid,
    SignerJournal,
    SignerNeedsRecovery,
    SignerReplay,
)

NOW = datetime(2026, 7, 23, 16, 35, 50, tzinfo=UTC)
SIGNER = "9zsJvRFTxAG5sBuXhjMDZkgWb9oqQbK8gDywo7mUMNKb"
OTHER_SIGNER = "11111111111111111111111111111111"
REQUEST_ID = "exec_sa_gw_002_live_20260723T163529Z"
COMMITMENT_HASH = "sha256:e5e6ec585f0e46a6a77a2c07c291d9bb1b0c02c9c375297abdf739b00421ee79"
MESSAGE_HASH = "sha256:85a6b98ca7c050ee9dcba7aa0750d876a8ef5fd084458e768200256a9950cba6"
MESSAGE_BASE64 = (
    "gAEAAgWFsHxvfs2yH1RgxBZctl8ZoLw6rc/w4PB7W+ABcqvB+oiiLZz5mG6tGo13"
    "1deKoFkkfkd38gqicxLl4LqSDiCYyExpveVZgDcjVfE+aGOlkifHBQKk+EaiEiUs"
    "I1/ioQoG3fbh12Whk9nL4UbO63msHLSF7V9bN5E6jPWFfv8AqRwL94kPv2krCiZw"
    "+yCBgni0b1KnXx+6CxMGt7TMCRavDj65uLmczb+f0v2jdSKLpjeKo+e29Dep1aB4"
    "aRxUXPEBAwQBBAIACgxAQg8AAAAAAAYA"
)
AUTHENTICITY_FIXTURE = b"fixture-only-foundry-authority"


class HmacAuthorizationVerifier:
    def verify(self, payload: bytes, signature: str) -> bool:
        expected = hmac.new(AUTHENTICITY_FIXTURE, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, f"test-hmac-sha256:{expected}")


class RecordingSigningProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[bytes, str]] = []

    def sign_exact_message(self, message: bytes, *, expected_signer: str) -> str:
        self.calls.append((message, expected_signer))
        if self.fail:
            raise TimeoutError("test response loss")
        digest = hashlib.sha256(b"test-signature:" + message).hexdigest()
        return f"test-signature:{digest}"


def prepared_execution() -> dict:
    return {
        "type": "prepared_execution",
        "protocol_version": "1.0.0",
        "execution_request_id": REQUEST_ID,
        "economic_plan_hash": (
            "sha256:d1cff2a760c7ca3b377e1f640abfea194b939d1a48385e0f0838d87aad5adfb3"
        ),
        "prepared_message_base64": MESSAGE_BASE64,
        "prepared_message_hash": MESSAGE_HASH,
        "execution_commitment_hash": COMMITMENT_HASH,
        "signer": SIGNER,
    }


def _signature(authorization: dict) -> str:
    payload = authorization_signing_payload(authorization)
    digest = hmac.new(AUTHENTICITY_FIXTURE, payload, hashlib.sha256).hexdigest()
    return f"test-hmac-sha256:{digest}"


def execution_authorization(
    *,
    authorization_id: str = "auth_sign_live_001",
    resign: bool = True,
    **changes: object,
) -> dict:
    authorization = {
        "type": "execution_authorization",
        "protocol_version": "1.0.0",
        "authorization_id": authorization_id,
        "execution_request_id": REQUEST_ID,
        "execution_commitment_hash": COMMITMENT_HASH,
        "prepared_message_hash": MESSAGE_HASH,
        "signer": SIGNER,
        "single_use": True,
        "issued_at": "2026-07-23T16:35:40Z",
        "expires_at": "2026-07-23T16:36:10Z",
    }
    authorization.update(changes)
    authorization["authorization_signature"] = _signature(authorization) if resign else "invalid"
    return authorization


def boundary(
    path: Path,
    provider: RecordingSigningProvider,
    *,
    signer_id: str = SIGNER,
) -> ExactMessageSigner:
    return ExactMessageSigner(
        SignerJournal(path),
        authorization_verifier=HmacAuthorizationVerifier(),
        signing_provider=provider,
        signer_id=signer_id,
    )


def test_live_authorization_signs_only_exact_prepared_bytes(tmp_path: Path) -> None:
    provider = RecordingSigningProvider()
    signer = boundary(tmp_path / "signer.sqlite3", provider)

    receipt = signer.sign(
        prepared_execution=prepared_execution(),
        authorization=execution_authorization(),
        now=NOW,
    )

    expected_message = base64.b64decode(MESSAGE_BASE64, validate=True)
    assert provider.calls == [(expected_message, SIGNER)]
    assert receipt["execution_commitment_hash"] == COMMITMENT_HASH
    assert receipt["prepared_message_hash"] == MESSAGE_HASH
    assert receipt["authorization_id"] == "auth_sign_live_001"
    assert signer.journal.status("auth_sign_live_001")["state"] == "signed"


def test_any_changed_message_byte_is_rejected_before_signing(tmp_path: Path) -> None:
    provider = RecordingSigningProvider()
    signer = boundary(tmp_path / "signer.sqlite3", provider)
    prepared = prepared_execution()
    message = bytearray(base64.b64decode(MESSAGE_BASE64, validate=True))
    message[-1] ^= 1
    prepared["prepared_message_base64"] = base64.b64encode(message).decode("ascii")

    with pytest.raises(SignerInvalid, match="exact prepared message bytes"):
        signer.sign(
            prepared_execution=prepared,
            authorization=execution_authorization(),
            now=NOW,
        )
    assert provider.calls == []


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("execution_request_id", "exec_other_001", "execution_request_id binding"),
        (
            "execution_commitment_hash",
            "sha256:" + "1" * 64,
            "execution_commitment_hash binding",
        ),
        ("prepared_message_hash", "sha256:" + "2" * 64, "prepared_message_hash binding"),
        ("signer", OTHER_SIGNER, "targets a different signer"),
    ],
)
def test_resigned_authorization_cannot_broaden_prepared_bindings(
    tmp_path: Path,
    field: str,
    value: object,
    error: str,
) -> None:
    provider = RecordingSigningProvider()
    signer = boundary(tmp_path / "signer.sqlite3", provider)

    with pytest.raises(SignerInvalid, match=error):
        signer.sign(
            prepared_execution=prepared_execution(),
            authorization=execution_authorization(**{field: value}),
            now=NOW,
        )
    assert provider.calls == []


def test_invalid_authorization_signature_never_reaches_signer(tmp_path: Path) -> None:
    provider = RecordingSigningProvider()
    signer = boundary(tmp_path / "signer.sqlite3", provider)

    with pytest.raises(SignerInvalid, match="signature verification failed"):
        signer.sign(
            prepared_execution=prepared_execution(),
            authorization=execution_authorization(resign=False),
            now=NOW,
        )
    assert provider.calls == []


@pytest.mark.parametrize(
    "changes,error_type,error",
    [
        ({"expires_at": "2026-07-23T16:35:50Z"}, SignerExpired, None),
        ({"issued_at": "2026-07-23T16:35:51Z"}, SignerInvalid, "future"),
        ({"single_use": False}, SignerInvalid, "single-use"),
    ],
)
def test_invalid_validity_never_reaches_signer(
    tmp_path: Path,
    changes: dict,
    error_type: type[Exception],
    error: str | None,
) -> None:
    provider = RecordingSigningProvider()
    signer = boundary(tmp_path / "signer.sqlite3", provider)

    with pytest.raises(error_type, match=error):
        signer.sign(
            prepared_execution=prepared_execution(),
            authorization=execution_authorization(**changes),
            now=NOW,
        )
    assert provider.calls == []


def test_consumption_and_replay_protection_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "signer.sqlite3"
    first_provider = RecordingSigningProvider()
    first = boundary(path, first_provider)
    first.sign(
        prepared_execution=prepared_execution(),
        authorization=execution_authorization(),
        now=NOW,
    )

    restarted_provider = RecordingSigningProvider()
    restarted = boundary(path, restarted_provider)
    assert restarted.journal.status("auth_sign_live_001")["state"] == "signed"
    with pytest.raises(SignerReplay):
        restarted.sign(
            prepared_execution=prepared_execution(),
            authorization=execution_authorization(),
            now=NOW,
        )
    assert restarted_provider.calls == []


def test_unknown_provider_outcome_requires_recovery_and_is_not_retried(tmp_path: Path) -> None:
    path = tmp_path / "signer.sqlite3"
    failing_provider = RecordingSigningProvider(fail=True)
    first = boundary(path, failing_provider)

    with pytest.raises(SignerNeedsRecovery):
        first.sign(
            prepared_execution=prepared_execution(),
            authorization=execution_authorization(),
            now=NOW,
        )
    assert len(failing_provider.calls) == 1
    assert first.journal.status("auth_sign_live_001")["state"] == "needs_recovery"

    restarted_provider = RecordingSigningProvider()
    restarted = boundary(path, restarted_provider)
    with pytest.raises(SignerNeedsRecovery):
        restarted.sign(
            prepared_execution=prepared_execution(),
            authorization=execution_authorization(),
            now=NOW,
        )
    assert restarted_provider.calls == []


def test_concurrent_use_reaches_signer_once(tmp_path: Path) -> None:
    path = tmp_path / "signer.sqlite3"
    provider = RecordingSigningProvider()

    def attempt() -> str:
        signer = boundary(path, provider)
        try:
            signer.sign(
                prepared_execution=prepared_execution(),
                authorization=execution_authorization(),
                now=NOW,
            )
            return "signed"
        except (SignerNeedsRecovery, SignerReplay):
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    assert sorted(results) == ["rejected", "signed"]
    assert len(provider.calls) == 1


def test_service_exposes_no_raw_key_rpc_or_broadcast_capability() -> None:
    source = Path(signer_module.__file__).read_text(encoding="utf-8").lower()

    for forbidden in (
        "private_key",
        "seed_phrase",
        "keypair",
        "sendtransaction",
        "send_transaction",
        "broadcast",
        "solana.rpc",
    ):
        assert forbidden not in source
