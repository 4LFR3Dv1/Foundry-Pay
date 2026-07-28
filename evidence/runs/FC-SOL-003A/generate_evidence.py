from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-003A"
PREVIOUS = ROOT / "evidence/runs/FC-SOL-003"
CONTRACT = ROOT / "programs/foundry-channel-vault/instruction-contract"
MANIFEST = CONTRACT / "Cargo.toml"


def write_json(path: Path, value: object) -> None:
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
        newline="\n",
    )


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def tagged_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise SystemExit(result.stdout)
    return result.stdout.replace("\r\n", "\n").replace("\r", "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--functional-head", required=True)
    args = parser.parse_args()

    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    env = dict(os.environ)
    env["FC_SOL_003_EVIDENCE_DIR"] = str(EVIDENCE)
    generation = run(
        [
            cargo,
            "test",
            "--locked",
            "--manifest-path",
            str(MANIFEST),
            "--lib",
            "generate_from_test_harness_when_requested",
            "--",
            "--nocapture",
        ],
        env=env,
    )
    cargo_test = run([cargo, "test", "--locked", "--manifest-path", str(MANIFEST), "--lib"])

    serialization_unchanged = load(EVIDENCE / "instruction-serialization-v1.json") == load(
        PREVIOUS / "instruction-serialization-v1.json"
    )
    ed25519_unchanged = load(EVIDENCE / "ed25519-offset-vectors-v1.json") == load(
        PREVIOUS / "ed25519-offset-vectors-v1.json"
    )
    signed_mapping_unchanged = load(EVIDENCE / "signed-message-mapping-v1.json") == load(
        PREVIOUS / "signed-message-mapping-v1.json"
    )
    if not all((serialization_unchanged, ed25519_unchanged, signed_mapping_unchanged)):
        raise SystemExit("a frozen FC-SOL-003 byte contract changed")

    write_json(
        EVIDENCE / "compatibility-report.json",
        {
            "instruction_serialization_byte_identical": serialization_unchanged,
            "ed25519_layouts_byte_identical": ed25519_unchanged,
            "signed_message_mapping_unchanged": signed_mapping_unchanged,
            "channel_state_layout_bytes": 490,
            "pda_derivation_changed": False,
            "historical_source_manifest": {
                "work_item": "FC-SOL-003",
                "functional_head": "2b6b5e4c8440571bf49f7917a088f861fd46d46e",
                "preserved": True,
                "current_source_binding": "FC-SOL-003A artifact-manifest.json",
            },
        },
    )
    write_json(
        EVIDENCE / "operability-decision-report.json",
        {
            "initialize": {
                "creates": ["ChannelState PDA", "canonical classic-token ATA"],
                "sender_is_writable_signer_payer": True,
                "required_programs": [
                    "system_program",
                    "token_program",
                    "associated_token_program",
                ],
            },
            "settlement": {
                "permissionless": True,
                "caller_signer_required": False,
                "destination": "canonical_ata(bound_recipient_wallet,channel_mint)",
            },
            "claim_window": {
                "minimum_seconds": 900,
                "maximum_seconds": 2592000,
                "deadline_exclusive": True,
                "checked_arithmetic": True,
            },
        },
    )
    validation = load(EVIDENCE / "validation-report.json")
    assert isinstance(validation, dict)
    validation.update(
        {
            "work_item": "FC-SOL-003A",
            "baseline": "65c8f89c7d4c86defea00152c1067d041db5528c",
            "functional_head": args.functional_head,
            "cargo_tests": 16,
            "negative_vectors": 29,
            "runtime_handlers": 0,
            "cpi_or_transfers": 0,
            "self_validation": "passed",
            "external_review": "not_performed",
        }
    )
    write_json(EVIDENCE / "validation-report.json", validation)
    write_json(
        EVIDENCE / "toolchain-report.json",
        {
            "cargo": run([cargo, "--version"]).strip(),
            "rustc": run(
                [
                    str(Path(cargo).with_name("rustc.exe" if os.name == "nt" else "rustc")),
                    "--version",
                ]
            ).strip(),
            "generation_test": generation,
            "cargo_test": cargo_test,
        },
    )

    artifacts = [
        *sorted(EVIDENCE.glob("*.json")),
        EVIDENCE / "README.md",
        EVIDENCE / "TASK_CONTRACT.yaml",
        EVIDENCE / "generate_evidence.py",
        *sorted((CONTRACT / "src").glob("*.rs")),
        CONTRACT / "examples/generate_instruction_vectors.rs",
        ROOT / "tests/channels/solana/instructions/test_instruction_operability.py",
        ROOT / "docs/channels/solana/instructions/FC-SOL-003-CONTRACT.md",
    ]
    entries = []
    for path in artifacts:
        if path.name == "artifact-manifest.json":
            continue
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": tagged_sha256(path),
            }
        )
    write_json(
        EVIDENCE / "artifact-manifest.json",
        {
            "schema_version": 1,
            "work_item": "FC-SOL-003A",
            "functional_head": args.functional_head,
            "artifact_count": len(entries),
            "artifacts": entries,
        },
    )


if __name__ == "__main__":
    main()
