from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/channel-protocol/python"))

from foundry_channel_protocol import (  # noqa: E402
    CanonicalizationError,
    canonical_json_bytes,
    parse_strict_json,
    sha256_canonical_json,
    sha256_raw_bytes,
    unsigned_record_projection,
    validate_amount_text,
    validate_canonical_set,
    validate_timestamp_text,
    validate_unsigned_integer,
    verify_declared_hash,
    verify_registered_domain,
    verify_self_hashed_record,
)
from foundry_channel_protocol.voucher import (  # noqa: E402
    canonical_voucher_payload,
    voucher_payload_hash,
)


CANON = ROOT / "contracts/channel/canonicalization"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", sorted((CANON / "positive").glob("*.json")))
def test_positive_vectors_publish_exact_bytes_and_hashes(path: Path) -> None:
    vector = load(path)
    if "source_bytes_hex" in vector:
        payload = bytes.fromhex(vector["source_bytes_hex"])
        assert len(payload) == vector["byte_length"]
        assert sha256_raw_bytes(payload) == vector["expected_sha256"]
        return
    parsed_source = parse_strict_json(vector["source_json"])
    assert parsed_source == vector["parsed_source"]
    if vector["profile_id"] == "signed-payload-v1":
        derived_projection = parsed_source["payload"]
    else:
        derived_projection = {
            key: value
            for key, value in parsed_source.items()
            if key not in vector["excluded_fields"]
        }
    assert derived_projection == vector["parsed_projection"]
    canonical = canonical_json_bytes(derived_projection)
    assert canonical.hex() == vector["canonical_utf8_hex"]
    assert base64.b64encode(canonical).decode("ascii") == vector["canonical_utf8_base64"]
    assert len(canonical) == vector["byte_length"]
    assert sha256_raw_bytes(canonical) == vector["expected_sha256"]


@pytest.mark.parametrize("path", sorted((CANON / "positive").glob("*.json")))
def test_positive_vector_source_objects_match_registered_schemas(path: Path) -> None:
    vector = load(path)
    if "source_bytes_hex" in vector:
        return
    domains = load(CANON / "domains.v1.json")["domains"]
    entry = next(item for item in domains if item["domain"] == vector["domain"])
    schema_path, _, fragment = entry["schema"].partition("#")
    schema_root = load((CANON / schema_path).resolve())
    validator = Draft202012Validator(schema_root)
    if fragment:
        target = schema_root
        for part in fragment.removeprefix("/").split("/"):
            target = target[part]
        validator = validator.evolve(schema=target)
    errors = sorted(
        validator.iter_errors(vector["parsed_source"]), key=lambda item: list(item.path)
    )
    assert errors == [], [error.message for error in errors]


def test_same_json_meaning_produces_same_bytes_and_hash() -> None:
    variants = [
        '{"b":"é","a":1}',
        '{ "a" : 1, "b" : "\\u00e9" }',
        '{"a":1,"b":"é"}',
    ]
    projections = [parse_strict_json(value) for value in variants]
    assert len({canonical_json_bytes(value) for value in projections}) == 1
    assert len({sha256_canonical_json(value) for value in projections}) == 1


def test_insertion_order_does_not_change_jcs() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


@pytest.mark.parametrize(
    ("wire", "code"),
    [
        ('{"a":1,"a":2}', "duplicate_key"),
        ('{"a":null}', "null_forbidden"),
        ('{"a":1.5}', "float_forbidden"),
        ('{"a":1e3}', "float_forbidden"),
        ('{"a":NaN}', "non_finite_number"),
        ('{"a":Infinity}', "non_finite_number"),
        ('{"a":-Infinity}', "non_finite_number"),
        ('{"a":-0}', "negative_zero"),
        ('{"a":9007199254740992}', "unsafe_integer"),
    ],
)
def test_strict_wire_rejections(wire: str, code: str) -> None:
    with pytest.raises(CanonicalizationError, match=code) as caught:
        parse_strict_json(wire)
    assert caught.value.code == code


def test_invalid_utf8_rejects() -> None:
    with pytest.raises(CanonicalizationError, match="invalid_utf8"):
        parse_strict_json(b'{"value":"\xff"}')


def test_lone_surrogate_rejects_but_valid_unicode_encodes_utf8() -> None:
    assert "c3a9" in canonical_json_bytes({"value": "é"}).hex()
    with pytest.raises(CanonicalizationError, match="lone_surrogate"):
        canonical_json_bytes({"value": "\ud800"})


def test_unicode_is_not_normalized() -> None:
    nfc = {"value": "é"}
    nfd = {"value": "e\u0301"}
    assert canonical_json_bytes(nfc) != canonical_json_bytes(nfd)
    assert sha256_canonical_json(nfc) != sha256_canonical_json(nfd)


@pytest.mark.parametrize("value", [True, False, -1, 9_007_199_254_740_992, 1.0, "1"])
def test_integer_validation_rejects_coercions_and_unsafe_values(value: object) -> None:
    with pytest.raises(CanonicalizationError, match="invalid_integer"):
        validate_unsigned_integer(value, path="$.sequence")


@pytest.mark.parametrize("value", ["01", "+1", "-1", "1.0", "1e3", " 1", "1 "])
def test_noncanonical_amounts_reject(value: str) -> None:
    with pytest.raises(CanonicalizationError, match="invalid_amount"):
        validate_amount_text(value, path="$.amount")


def test_u64_boundary() -> None:
    assert validate_amount_text("18446744073709551615", path="$.amount")
    with pytest.raises(CanonicalizationError, match="amount_out_of_range"):
        validate_amount_text("18446744073709551616", path="$.amount")


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-01T00:00:00.000Z",
        "2026-08-01T00:00:00+00:00",
        "2026-08-01 00:00:00Z",
        "2026-08-01T00:00:00",
        "2026-02-30T00:00:00Z",
    ],
)
def test_timestamp_profile_rejects_noncanonical_or_impossible_values(value: str) -> None:
    with pytest.raises(CanonicalizationError, match="invalid_timestamp"):
        validate_timestamp_text(value, path="$.created_at")


def test_self_hash_excludes_exactly_one_field() -> None:
    unsigned = {"type": "record", "protocol_version": "1.0.0", "value": "x"}
    record = {**unsigned, "receipt_hash": sha256_canonical_json(unsigned)}
    projection = unsigned_record_projection(record, "receipt_hash")
    assert projection == unsigned
    assert sha256_canonical_json(projection) == record["receipt_hash"]
    assert verify_self_hashed_record(record, "receipt_hash") == unsigned
    with pytest.raises(CanonicalizationError, match="own_hash_missing"):
        unsigned_record_projection(unsigned, "receipt_hash")
    wrongly_hashed = {
        **unsigned,
        "receipt_hash": sha256_canonical_json({**unsigned, "receipt_hash": "sha256:" + "0" * 64}),
    }
    with pytest.raises(CanonicalizationError, match="hash_mismatch"):
        verify_self_hashed_record(wrongly_hashed, "receipt_hash")


def test_hash_text_is_lowercase_fixed_length_and_exact() -> None:
    valid = "sha256:" + "a" * 64
    verify_declared_hash(valid, valid)
    for invalid in ("sha256:" + "A" * 64, "sha256:abcd", "a" * 64):
        with pytest.raises(CanonicalizationError, match="invalid_hash"):
            verify_declared_hash(invalid, valid)
    with pytest.raises(CanonicalizationError, match="hash_mismatch"):
        verify_declared_hash(valid, "sha256:" + "b" * 64)


def test_canonical_set_rejects_duplicates_and_noncanonical_order() -> None:
    assert validate_canonical_set(["a", "b"], path="$.items") == ["a", "b"]
    with pytest.raises(CanonicalizationError, match="canonical_set_duplicate"):
        validate_canonical_set(["a", "a"], path="$.items")
    with pytest.raises(CanonicalizationError, match="canonical_set_order"):
        validate_canonical_set(["b", "a"], path="$.items")


def test_domains_require_exact_registry_match_not_prefixes() -> None:
    verify_registered_domain({"domain": "foundry.channels.voucher"}, "foundry.channels.voucher")
    verify_registered_domain(
        {"type": "settlement_request", "protocol_version": "1.0.0"},
        "foundry.channels.settlement-request",
    )
    with pytest.raises(CanonicalizationError, match="domain_unregistered"):
        verify_registered_domain(
            {"domain": "foundry.channels.voucher.extra"},
            "foundry.channels.voucher.extra",
        )
    with pytest.raises(CanonicalizationError, match="domain_mismatch"):
        verify_registered_domain(
            {"type": "settlement_request_extra", "protocol_version": "1.0.0"},
            "foundry.channels.settlement-request",
        )


def test_voucher_unknown_missing_and_null_fields_fail_before_hashing() -> None:
    vector = load(ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json")
    payload = vector["vouchers"][-1]["payload"]
    unknown = {**payload, "unknown": "forbidden"}
    missing = dict(payload)
    missing.pop("mint")
    null_value = {**payload, "mint": None}
    for candidate, code in (
        (unknown, "unknown_field"),
        (missing, "missing_field"),
        (null_value, "invalid_string"),
    ):
        with pytest.raises(ValueError, match=code):
            canonical_voucher_payload(candidate)


def test_material_voucher_mutations_change_bytes_hash_and_reject_stale_hash() -> None:
    vector = load(ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json")
    payload = vector["vouchers"][-1]["payload"]
    original_bytes = canonical_voucher_payload(payload)
    original_hash = voucher_payload_hash(payload)
    fields = [
        "domain",
        "network",
        "genesis_hash",
        "program_id",
        "channel_id",
        "epoch",
        "recipient_claim_pubkey",
        "mint",
        "sequence",
        "expires_at",
        "cumulative_authorized_base_units",
    ]
    for field in fields:
        mutated = copy.deepcopy(payload)
        if isinstance(mutated[field], int):
            mutated[field] += 1
        elif field == "cumulative_authorized_base_units":
            mutated[field] = str(int(mutated[field]) + 1)
        else:
            mutated[field] += "x"
        assert canonical_json_bytes(mutated) != original_bytes
        assert sha256_canonical_json(mutated) != original_hash
        with pytest.raises(CanonicalizationError, match="hash_mismatch"):
            verify_declared_hash(original_hash, sha256_canonical_json(mutated))


def test_signatures_do_not_change_signed_payload_hashes() -> None:
    voucher_vector = load(
        ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json"
    )
    voucher = copy.deepcopy(voucher_vector["vouchers"][-1])
    original = voucher_payload_hash(voucher["payload"])
    voucher["sender_signature"] = voucher["sender_signature"][::-1]
    assert voucher_payload_hash(voucher["payload"]) == original

    binding_vector = load(
        ROOT / "contracts/channel/test-vectors/positive/recipient-binding-initial-v1.json"
    )
    binding = copy.deepcopy(binding_vector["binding"])
    original_bytes = canonical_json_bytes(binding["payload"])
    binding["claim_key_signature"] = binding["claim_key_signature"][::-1]
    binding["destination_wallet_signature"] = binding["destination_wallet_signature"][::-1]
    assert canonical_json_bytes(binding["payload"]) == original_bytes


def test_legacy_voucher_and_binding_hashes_remain_exact() -> None:
    voucher_vector = load(
        ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json"
    )
    voucher = voucher_vector["vouchers"][-1]
    assert voucher_payload_hash(voucher["payload"]) == voucher["voucher_hash"]
    binding_vector = load(
        ROOT / "contracts/channel/test-vectors/positive/recipient-binding-initial-v1.json"
    )
    binding = binding_vector["binding"]
    assert sha256_raw_bytes(canonical_json_bytes(binding["payload"])) == binding["binding_hash"]


def test_profile_and_domain_registries_are_closed_and_consistent() -> None:
    profiles = load(CANON / "profiles.v1.json")
    domains = load(CANON / "domains.v1.json")
    profile_ids = {item["profile_id"] for item in profiles["profiles"]}
    names = [item["domain"] for item in domains["domains"]]
    assert len(names) == len(set(names))
    assert all(item["profile_id"] in profile_ids for item in domains["domains"])
    assert all(item["version"] == "1.0.0" for item in domains["domains"])
    assert all(item["excluded_fields"] is not None for item in domains["domains"])


def test_journal_profile_documentation_matches_registered_preimage() -> None:
    profile_document = (ROOT / "docs/channels/HASH_PROFILES.md").read_text(encoding="utf-8")
    documented_fields = """type
protocol_version
settlement_id or refund_id
sequence
state
event_type
payload
payload_hash
previous_event_hash
recorded_at"""
    assert documented_fields in profile_document
    assert "`event_hash` is excluded" in profile_document
    assert "excluding only `event_hash`" in profile_document

    journal_domains = [
        entry
        for entry in load(CANON / "domains.v1.json")["domains"]
        if entry["profile_id"] == "journal-chain-v1"
    ]
    assert journal_domains
    assert all(entry["excluded_fields"] == ["event_hash"] for entry in journal_domains)


def test_every_registered_schema_and_fragment_exists() -> None:
    domains = load(CANON / "domains.v1.json")["domains"]
    for entry in domains:
        schema_path, _, fragment = entry["schema"].partition("#")
        resolved = (CANON / schema_path).resolve()
        assert resolved.is_file(), (entry["domain"], resolved)
        schema = load(resolved)
        if fragment:
            target = schema
            for part in fragment.removeprefix("/").split("/"):
                assert part in target, (entry["domain"], part)
                target = target[part]
            assert isinstance(target, dict)


def test_manifest_lists_every_vector_once() -> None:
    manifest = load(CANON / "manifest.v1.json")
    assert manifest["positive_vectors"] == sorted(
        path.name for path in (CANON / "positive").glob("*.json")
    )
    assert manifest["negative_vectors"] == sorted(
        path.name for path in (CANON / "negative").glob("*.json")
    )


@pytest.mark.parametrize("path", sorted((CANON / "negative").glob("*.json")))
def test_every_negative_vector_rejects_at_declared_stage(path: Path) -> None:
    vector = load(path)
    vector_id = vector["vector_id"]
    expected_code = vector["expected_rejection_code"]
    voucher_fixture = load(
        ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json"
    )
    voucher_payload = voucher_fixture["vouchers"][-1]["payload"]

    def exercise() -> None:
        if vector_id in {
            "duplicate-keys",
            "float",
            "nan",
            "infinity",
            "negative-zero",
            "null",
            "unsafe-integer",
        }:
            parse_strict_json(vector["input"])
        elif vector_id == "unknown-field":
            canonical_voucher_payload({**voucher_payload, "unknown": True})
        elif vector_id == "missing-field":
            candidate = dict(voucher_payload)
            candidate.pop("mint")
            canonical_voucher_payload(candidate)
        elif vector_id == "bool-as-integer":
            validate_unsigned_integer(vector["input"], path="$.sequence")
        elif vector_id in {"u64-overflow", "amount-leading-zero"}:
            validate_amount_text(vector["input"], path="$.amount")
        elif vector_id == "malformed-timestamp":
            validate_timestamp_text(vector["input"], path="$.created_at")
        elif vector_id == "lone-surrogate":
            canonical_json_bytes({"value": "\ud800"})
        elif vector_id == "unregistered-domain":
            verify_registered_domain({"domain": vector["input"]}, vector["input"])
        elif vector_id in {"uppercase-hash", "short-hash"}:
            verify_declared_hash(vector["input"], "sha256:" + "a" * 64)
        elif vector_id == "own-hash-in-preimage":
            verify_self_hashed_record(vector["input"], "receipt_hash")
        elif vector_id in {"canonical-set-order", "canonical-set-duplicate"}:
            validate_canonical_set(vector["input"], path="$.items")
        else:  # pragma: no cover - makes new unimplemented vectors fail loudly
            raise AssertionError(f"negative vector has no executor: {vector_id}")

    with pytest.raises(Exception) as caught:
        exercise()
    observed = getattr(caught.value, "code", None)
    if observed is None:
        message = str(caught.value)
        assert expected_code in message
    else:
        assert observed == expected_code
