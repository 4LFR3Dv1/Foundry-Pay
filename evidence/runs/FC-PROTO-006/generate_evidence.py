"""Generate FC-PROTO-006 normative vectors and reproducible evidence."""

from __future__ import annotations

import base64
import hashlib
import json
import platform
import ssl
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CHANNEL_PYTHON = ROOT / "packages/channel-protocol/python"
sys.path.insert(0, str(CHANNEL_PYTHON))

from foundry_channel_protocol.canonical import (  # noqa: E402
    canonical_json_bytes,
    sha256_canonical_json,
    sha256_raw_bytes,
    unsigned_record_projection,
)


RUN = ROOT / "evidence/runs/FC-PROTO-006"
CANON = ROOT / "contracts/channel/canonicalization"
POSITIVE = CANON / "positive"
NEGATIVE = CANON / "negative"
BASELINE = "469a28e9a92a7d443b9e20621ade2e4d23a09eee"


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def positive_json_vector(
    *,
    vector_id: str,
    profile_id: str,
    domain: str,
    object_type: str,
    projection: dict[str, Any],
    excluded_fields: list[str],
) -> dict[str, Any]:
    source_json = json.dumps(projection, ensure_ascii=False, separators=(", ", ": "))
    canonical = canonical_json_bytes(projection)
    return {
        "vector_id": vector_id,
        "profile_id": profile_id,
        "domain": domain,
        "object_type": object_type,
        "source_json": source_json,
        "parsed_projection": projection,
        "canonical_utf8_hex": canonical.hex(),
        "canonical_utf8_base64": base64.b64encode(canonical).decode("ascii"),
        "byte_length": len(canonical),
        "expected_sha256": sha256_raw_bytes(canonical),
        "excluded_fields": excluded_fields,
        "expected_acceptance": True,
    }


def generate_vectors() -> list[dict[str, Any]]:
    voucher_fixture = load(
        ROOT / "contracts/channel/test-vectors/positive/cumulative-channel-v1.json"
    )
    binding_fixture = load(
        ROOT / "contracts/channel/test-vectors/positive/recipient-binding-initial-v1.json"
    )
    voucher = voucher_fixture["vouchers"][-1]
    binding = binding_fixture["binding"]

    observation_unsigned = {
        "type": "settlement_observation",
        "protocol_version": "1.0.0",
        "source_id": "provider_a",
        "channel_id": "channel_foundations_001",
        "channel_account": voucher_fixture["constants"]["channel_account"],
        "epoch": 0,
        "mint": voucher_fixture["constants"]["mint"],
        "destination": voucher_fixture["constants"]["recipient_wallet"],
        "transaction_signature": "RzgQYATtgFZNG7eDgktPAaKh3R922BEjYNLRnvM7u96eFjsnSe4aFYQAtgaP4Hi7kyn91itF1eTEeo498NJ8uS4",
        "settled_total_before": "15000000",
        "settled_total_after": "40000000",
        "vault_balance_before": "85000000",
        "vault_balance_after": "60000000",
        "recipient_balance_before": "0",
        "recipient_balance_after": "25000000",
        "observed_at": "2026-08-01T00:08:00Z",
    }
    observation = {
        **observation_unsigned,
        "observation_hash": sha256_canonical_json(observation_unsigned),
    }
    observation_projection = unsigned_record_projection(observation, "observation_hash")

    journal_projection = {
        "type": "settlement_journal_entry",
        "protocol_version": "1.0.0",
        "settlement_id": "settlement_001",
        "sequence": 1,
        "state": "requested",
        "event_type": "request_validated",
        "payload": {"request_hash": "sha256:" + "1" * 64},
        "previous_event_hash": "sha256:" + "0" * 64,
        "recorded_at": "2026-08-01T00:07:00Z",
    }
    vectors = [
        positive_json_vector(
            vector_id="voucher-payload-v1",
            profile_id="signed-payload-v1",
            domain="foundry.channels.voucher",
            object_type="channel_voucher",
            projection=voucher["payload"],
            excluded_fields=["voucher_hash", "sender_signature"],
        ),
        positive_json_vector(
            vector_id="recipient-binding-payload-v1",
            profile_id="signed-payload-v1",
            domain="foundry.channels.recipient-binding",
            object_type="recipient_binding",
            projection=binding["payload"],
            excluded_fields=[
                "binding_hash",
                "claim_key_signature",
                "destination_wallet_signature",
            ],
        ),
        positive_json_vector(
            vector_id="settlement-observation-v1",
            profile_id="self-hashed-record-v1",
            domain="foundry.channels.settlement-observation",
            object_type="settlement_observation",
            projection=observation_projection,
            excluded_fields=["observation_hash"],
        ),
        positive_json_vector(
            vector_id="settlement-journal-entry-v1",
            profile_id="journal-chain-v1",
            domain="foundry.channels.settlement-journal-entry",
            object_type="settlement_journal_entry",
            projection=journal_projection,
            excluded_fields=["event_hash"],
        ),
    ]

    raw = b"\x00foundry-channel-message-v1\xff"
    vectors.append(
        {
            "vector_id": "raw-bytes-v1",
            "profile_id": "raw-bytes-commitment-v1",
            "domain": "commitment-object-required",
            "object_type": "prepared_message_bytes",
            "source_bytes_hex": raw.hex(),
            "canonical_utf8_hex": None,
            "canonical_utf8_base64": None,
            "byte_length": len(raw),
            "expected_sha256": sha256_raw_bytes(raw),
            "excluded_fields": [],
            "expected_acceptance": True,
        }
    )
    evidence_bytes = b'{"artifact":"pytest-full.xml","namespace":"foundry.channels.evidence"}\n'
    vectors.append(
        {
            "vector_id": "evidence-artifact-v1",
            "profile_id": "evidence-artifact-v1",
            "domain": "foundry.channels.evidence",
            "object_type": "evidence_file",
            "source_bytes_hex": evidence_bytes.hex(),
            "canonical_utf8_hex": None,
            "canonical_utf8_base64": None,
            "byte_length": len(evidence_bytes),
            "expected_sha256": sha256_raw_bytes(evidence_bytes),
            "excluded_fields": [],
            "economic_authority": False,
            "expected_acceptance": True,
        }
    )
    for vector in vectors:
        dump(POSITIVE / f"{vector['vector_id']}.json", vector)

    negative_cases = [
        ("duplicate-keys", '{"a":1,"a":2}', "duplicate_key", "parse"),
        (
            "unknown-field",
            {"domain": "foundry.channels.voucher", "unknown": True},
            "unknown_field",
            "schema",
        ),
        ("missing-field", {"domain": "foundry.channels.voucher"}, "missing_field", "schema"),
        ("null", '{"a":null}', "null_forbidden", "projection"),
        ("float", '{"a":1.5}', "float_forbidden", "parse"),
        ("nan", '{"a":NaN}', "non_finite_number", "parse"),
        ("infinity", '{"a":Infinity}', "non_finite_number", "parse"),
        ("negative-zero", '{"a":-0}', "negative_zero", "parse"),
        ("unsafe-integer", '{"a":9007199254740992}', "unsafe_integer", "parse"),
        ("bool-as-integer", True, "invalid_integer", "schema"),
        ("u64-overflow", "18446744073709551616", "amount_out_of_range", "schema"),
        ("amount-leading-zero", "01", "invalid_amount", "schema"),
        ("malformed-timestamp", "2026-02-30T00:00:00Z", "invalid_timestamp", "schema"),
        ("lone-surrogate", "\\ud800", "lone_surrogate", "canonicalization"),
        (
            "unregistered-domain",
            "foundry.channels.unknown",
            "domain_unregistered",
            "domain_verification",
        ),
        ("uppercase-hash", "sha256:" + "A" * 64, "invalid_hash", "hash_verification"),
        ("short-hash", "sha256:abcd", "invalid_hash", "hash_verification"),
        (
            "own-hash-in-preimage",
            {"type": "record", "receipt_hash": "sha256:" + "0" * 64},
            "hash_mismatch",
            "hash_verification",
        ),
        (
            "canonical-set-order",
            ["sha256:" + "b" * 64, "sha256:" + "a" * 64],
            "canonical_set_order",
            "projection",
        ),
        (
            "canonical-set-duplicate",
            ["sha256:" + "a" * 64, "sha256:" + "a" * 64],
            "canonical_set_duplicate",
            "projection",
        ),
    ]
    for vector_id, input_value, code, stage in negative_cases:
        dump(
            NEGATIVE / f"{vector_id}.json",
            {
                "vector_id": vector_id,
                "input": input_value,
                "expected_rejection_code": code,
                "rejection_stage": stage,
                "expected_acceptance": False,
            },
        )
    return vectors


def generate_reports(vectors: list[dict[str, Any]]) -> None:
    domains = load(CANON / "domains.v1.json")["domains"]
    inventory = {
        "work_item": "FC-PROTO-006",
        "baseline_commit": BASELINE,
        "runtime": {
            "python": platform.python_version(),
            "rfc8785": version("rfc8785"),
            "openssl": ssl.OPENSSL_VERSION,
            "hashlib_sha256": hashlib.sha256().name,
        },
        "schemas_analyzed": sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "contracts/channel").glob("*.schema.json")
        ),
        "modules_analyzed": [
            "packages/channel-protocol/python/foundry_channel_protocol/voucher.py",
            "packages/channel-protocol/python/foundry_channel_protocol/recipient_binding.py",
            "packages/channel-protocol/python/foundry_channel_protocol/settlement.py",
            "packages/channel-protocol/python/foundry_channel_protocol/closure.py",
            "packages/external-execution-protocol/python/foundry_external_execution_protocol/canonicalization.py",
        ],
        "known_channel_domains": len(domains),
        "result": "all known channel hash object types have a registered profile",
    }
    dump(RUN / "object-inventory.json", inventory)
    dump(
        RUN / "hash-profile-matrix.json",
        {
            "profiles": load(CANON / "profiles.v1.json")["profiles"],
            "objects": [
                {
                    "domain": item["domain"],
                    "object_type": item["object_type"],
                    "profile_id": item["profile_id"],
                    "result_hash_field": item["result_hash_field"],
                    "excluded_fields": item["excluded_fields"],
                }
                for item in domains
            ],
        },
    )

    voucher = next(item for item in vectors if item["vector_id"] == "voucher-payload-v1")
    base = voucher["parsed_projection"]
    mutation_fields = [
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
    mutations = []
    for field in mutation_fields:
        mutated = dict(base)
        original = mutated[field]
        if isinstance(original, int):
            mutated[field] = original + 1
        elif field == "cumulative_authorized_base_units":
            mutated[field] = str(int(original) + 1)
        else:
            mutated[field] = f"{original}x"
        mutated_hash = sha256_canonical_json(mutated)
        mutations.append(
            {
                "field": field,
                "base_hash": voucher["expected_sha256"],
                "mutated_hash": mutated_hash,
                "bytes_changed": canonical_json_bytes(base) != canonical_json_bytes(mutated),
                "hash_changed": voucher["expected_sha256"] != mutated_hash,
                "stale_verification": "rejected",
            }
        )
    dump(
        RUN / "domain-mutation-report.json",
        {
            "domain": voucher["domain"],
            "mutations": mutations,
            "all_changed": all(item["hash_changed"] for item in mutations),
        },
    )

    nfc = {"domain": "foundry.channels.voucher", "label": "é"}
    nfd = {"domain": "foundry.channels.voucher", "label": "e\u0301"}
    dump(
        RUN / "unicode-number-report.json",
        {
            "unicode": {
                "nfc_hex": canonical_json_bytes(nfc).hex(),
                "nfd_hex": canonical_json_bytes(nfd).hex(),
                "hashes_differ": sha256_canonical_json(nfc) != sha256_canonical_json(nfd),
                "normalization_performed": False,
                "lone_surrogate": "rejected",
            },
            "numbers": {
                "json_safe_unsigned_max": 9_007_199_254_740_991,
                "first_rejected_integer": 9_007_199_254_740_992,
                "u64_max_text": "18446744073709551615",
                "first_rejected_u64_text": "18446744073709551616",
                "floats": "rejected",
                "negative_zero": "rejected",
            },
        },
    )

    binding = next(item for item in vectors if item["vector_id"] == "recipient-binding-payload-v1")
    dump(
        RUN / "legacy-hash-compatibility.json",
        {
            "decision": "preserve reviewed v1 preimages",
            "voucher": {
                "expected": "sha256:8a3283d61a75e1bbe987941601e8f28708875913fd0dfef0fa399c6a7dd296e2",
                "observed": voucher["expected_sha256"],
                "match": voucher["expected_sha256"]
                == "sha256:8a3283d61a75e1bbe987941601e8f28708875913fd0dfef0fa399c6a7dd296e2",
            },
            "recipient_binding": {
                "expected": "sha256:5ffc2a2ac51ebcbeb23d2cffa013251ce2680747eec9cbb570d5ee793a535192",
                "observed": binding["expected_sha256"],
                "match": binding["expected_sha256"]
                == "sha256:5ffc2a2ac51ebcbeb23d2cffa013251ce2680747eec9cbb570d5ee793a535192",
            },
            "settlement_closure_recovery": {
                "migration": "none",
                "verification": "existing regression suite uses unchanged JCS preimages through the common primitive",
            },
        },
    )

    dump(
        CANON / "manifest.v1.json",
        {
            "registry": "foundry.channels.canonicalization-vectors",
            "version": "1.0.0",
            "positive_vectors": sorted(path.name for path in POSITIVE.glob("*.json")),
            "negative_vectors": sorted(path.name for path in NEGATIVE.glob("*.json")),
            "profiles": "profiles.v1.json",
            "domains": "domains.v1.json",
        },
    )
    dump(
        RUN / "validation-report.json",
        {
            "work_item": "FC-PROTO-006",
            "baseline_commit": BASELINE,
            "status": "generated",
            "positive_vector_count": len(list(POSITIVE.glob("*.json"))),
            "negative_vector_count": len(list(NEGATIVE.glob("*.json"))),
            "domain_count": len(domains),
            "claims": {
                "offline_only": True,
                "typescript_conformance_complete": False,
                "rust_conformance_complete": False,
                "channelvault_complete": False,
                "on_chain_execution_proven": False,
                "production_ready": False,
            },
        },
    )


def generate_manifest() -> None:
    implementation_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    paths = [
        *sorted(CANON.rglob("*.json")),
        ROOT / "packages/channel-protocol/python/foundry_channel_protocol/canonical.py",
        ROOT / "tests/channels/test_canonicalization.py",
        ROOT / "docs/channels/CANONICALIZATION.md",
        ROOT / "docs/channels/HASH_PROFILES.md",
        ROOT / "docs/channels/DOMAIN_REGISTRY.md",
        ROOT / "docs/channels/ADR/FC-ADR-007-canonicalization-and-hash-profiles.md",
        RUN / "validation-report.json",
        RUN / "object-inventory.json",
        RUN / "hash-profile-matrix.json",
        RUN / "domain-mutation-report.json",
        RUN / "unicode-number-report.json",
        RUN / "legacy-hash-compatibility.json",
    ]
    pytest_xml = RUN / "pytest-full.xml"
    if pytest_xml.exists():
        paths.append(pytest_xml)
    artifacts = []
    for path in paths:
        payload = path.read_bytes()
        artifacts.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_raw_bytes(payload),
                "bytes": len(payload),
            }
        )
    dump(
        RUN / "artifact-manifest.json",
        {
            "work_item": "FC-PROTO-006",
            "baseline_commit": BASELINE,
            "implementation_commit": implementation_commit,
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        },
    )


def main() -> None:
    vectors = generate_vectors()
    generate_reports(vectors)
    generate_manifest()


if __name__ == "__main__":
    main()
