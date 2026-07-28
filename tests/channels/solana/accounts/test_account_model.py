from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from solders.pubkey import Pubkey


ROOT = Path(__file__).parents[4]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-002"


def load(name: str) -> object:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_layout_is_contiguous_fixed_width_and_exactly_490_bytes() -> None:
    layout = load("account-layout-v1.json")
    assert isinstance(layout, dict)
    assert layout["space"] == 490
    assert layout["variable_width_fields"] is False

    expected_offset = 0
    for field in layout["fields"]:
        assert field["offset"] == expected_offset
        expected_offset = field["end_exclusive"]
    assert expected_offset == layout["space"]


def test_serialized_vectors_publish_exact_bytes_and_hashes() -> None:
    vectors = load("serialized-golden-vectors-v1.json")
    assert isinstance(vectors, list)
    assert {vector["vector_id"] for vector in vectors} == {
        "zero-initialized",
        "funded-active",
        "closing-bound",
    }

    for vector in vectors:
        raw = bytes.fromhex(vector["bytes_hex"])
        assert base64.b64decode(vector["bytes_base64"]) == raw
        assert len(raw) == vector["byte_length"] == 490
        assert f"sha256:{hashlib.sha256(raw).hexdigest()}" == vector["sha256"]
        assert raw[:8].hex() == hashlib.sha256(b"account:ChannelState").digest()[:8].hex()


def test_pda_vectors_are_independently_reproduced_with_solders() -> None:
    vectors = load("pda-vectors-v1.json")
    assert isinstance(vectors, list)

    addresses: set[str] = set()
    for vector in vectors:
        program_id = Pubkey.from_string(vector["program_id"])
        sender = bytes(Pubkey.from_string(vector["sender"]))
        mint = bytes(Pubkey.from_string(vector["mint"]))
        nonce = bytes.fromhex(vector["channel_nonce_hex"])
        pda, bump = Pubkey.find_program_address(
            [b"channel", sender, mint, nonce],
            program_id,
        )
        assert str(pda) == vector["expected_pda"]
        assert bump == vector["expected_bump"]
        addresses.add(str(pda))

    assert len(addresses) == len(vectors)


def test_token_boundary_and_rent_claims_remain_narrow() -> None:
    token_report = load("token-account-authority-report.json")
    assert isinstance(token_report, list)
    decisions = {case["case"]: case["decision"] for case in token_report}
    assert decisions["exact-classic-vault"] == "accepted"
    assert decisions["token-2022-owner"] == "rejected"
    assert decisions["wrong-mint"] == "rejected"
    assert decisions["wrong-authority"] == "rejected"

    rent = load("rent-space-report.json")
    assert isinstance(rent, dict)
    assert rent["normative"] == {"channel_state_space": 490}
    assert rent["environmental"]["minimum_balance_lamports"] > 0
    assert rent["environmental"]["lamports_are_not_a_protocol_constant"] is True

    pda_vectors = load("pda-vectors-v1.json")
    serialized = load("serialized-golden-vectors-v1.json")
    assert isinstance(pda_vectors, list)
    assert isinstance(serialized, list)
    base_pda = Pubkey.from_string(pda_vectors[0]["expected_pda"])
    mint = Pubkey.from_string(serialized[0]["decoded"]["mint"])
    token_program = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    associated_program = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
    expected_vault, _ = Pubkey.find_program_address(
        [bytes(base_pda), bytes(token_program), bytes(mint)],
        associated_program,
    )
    assert str(expected_vault) == serialized[0]["decoded"]["vault_account_public_key"]


def test_artifact_manifest_recalculates_for_every_bound_file() -> None:
    manifest = load("artifact-manifest.json")
    assert isinstance(manifest, dict)
    functional_head = manifest["functional_head"]
    assert isinstance(functional_head, str)
    assert len(functional_head) == 40
    assert all(character in "0123456789abcdef" for character in functional_head)
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        raw = path.read_bytes()
        assert len(raw) == artifact["byte_length"]
        assert f"sha256:{hashlib.sha256(raw).hexdigest()}" == artifact["sha256"]


def test_account_model_contains_no_variable_width_or_instruction_surface() -> None:
    source = (ROOT / "programs/foundry-channel-vault/src/state.rs").read_text(encoding="utf-8")
    struct_body = source.split("pub struct ChannelState {", 1)[1].split("\n}", 1)[0]
    assert "Vec<" not in struct_body
    assert "String" not in struct_body
    assert "Option<" not in struct_body

    all_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "programs/foundry-channel-vault/src").glob("*.rs")
    )
    assert "entrypoint!" not in all_source
    assert "invoke(" not in all_source
    assert "invoke_signed(" not in all_source
    assert "transfer_checked" not in all_source
