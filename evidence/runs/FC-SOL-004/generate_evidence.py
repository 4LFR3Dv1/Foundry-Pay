#!/usr/bin/env python3
"""Generate the reproducible FC-SOL-004 evidence pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
TRANSITION_MANIFEST = ROOT / "programs/foundry-channel-vault/transition-model/Cargo.toml"
CONTRACT_MANIFEST = ROOT / "programs/foundry-channel-vault/instruction-contract/Cargo.toml"
PINNED_RUST_TOOLCHAIN = "+1.85.1"


def cargo() -> str:
    executable = shutil.which("cargo")
    if executable:
        return executable
    candidate = Path.home() / ".cargo" / "bin" / ("cargo.exe" if os.name == "nt" else "cargo")
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("cargo not found")


def rustc() -> str:
    executable = shutil.which("rustc")
    if executable:
        return executable
    candidate = Path.home() / ".cargo" / "bin" / ("rustc.exe" if os.name == "nt" else "rustc")
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("rustc not found")


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout + completed.stderr


def write_json(name: str, value: object) -> None:
    (EVIDENCE / name).write_bytes(
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    cargo_bin = cargo()

    transition_output = run(
        [
            cargo_bin,
            PINNED_RUST_TOOLCHAIN,
            "test",
            "--manifest-path",
            str(TRANSITION_MANIFEST),
        ]
    )
    contract_output = run(
        [
            cargo_bin,
            PINNED_RUST_TOOLCHAIN,
            "test",
            "--manifest-path",
            str(CONTRACT_MANIFEST),
        ]
    )
    (EVIDENCE / "cargo-test-transition-model.txt").write_bytes(
        transition_output.replace("\r\n", "\n").encode("utf-8")
    )
    (EVIDENCE / "cargo-test-instruction-contract.txt").write_bytes(
        contract_output.replace("\r\n", "\n").encode("utf-8")
    )

    bounded_path = EVIDENCE / "bounded-exploration-report.json"
    run(
        [
            cargo_bin,
            PINNED_RUST_TOOLCHAIN,
            "run",
            "--manifest-path",
            str(TRANSITION_MANIFEST),
            "--example",
            "bounded_explorer",
            "--",
            str(bounded_path),
        ]
    )
    bounded = json.loads(bounded_path.read_text(encoding="utf-8"))
    if bounded["invariant_violations"] != 0:
        raise RuntimeError("bounded exploration found an invariant violation")

    with tempfile.TemporaryDirectory() as temporary:
        env = os.environ.copy()
        env["FC_SOL_003_EVIDENCE_DIR"] = temporary
        run(
            [
                cargo_bin,
                PINNED_RUST_TOOLCHAIN,
                "test",
                "--manifest-path",
                str(CONTRACT_MANIFEST),
            ],
            env=env,
        )
        for name in (
            "account-meta-contracts-v1.json",
            "instruction-registry-v1.json",
        ):
            shutil.copy2(Path(temporary) / name, EVIDENCE / name)

    write_json(
        "property-report.json",
        {
            "work_item": "FC-SOL-004",
            "framework": "proptest",
            "version": "1.6.0",
            "configuration": {
                "cases_per_property": 512,
                "max_shrink_iterations": 4096,
                "failure_persistence": "proptest-regressions when a counterexample exists",
            },
            "properties": [
                "arbitrary_valid_economic_path_preserves_invariants",
                "rejected_settlement_never_changes_input_state",
                "arbitrary_instruction_sequences_preserve_invariants_or_reject_atomically",
            ],
            "total_generated_cases": 1536,
            "minimized_counterexamples": [],
            "result": "passed",
        },
    )
    write_json(
        "invariant-matrix.json",
        {
            "economic": [
                "settled <= activated",
                "activated + refunded <= funded",
                "funded, activated, settled, and refunded are monotonic",
            ],
            "authority": [
                "sequence strictly advances",
                "binding nonce is consumed at most once",
                "recipient is immutable after binding",
                "caller identity and obligation_hash do not affect settlement economics",
            ],
            "lifecycle": [
                "finalized is terminal",
                "activation is allowed only before the exclusive claim deadline",
                "activated rights remain settleable after the deadline",
            ],
            "topology": [
                "initialize pre-owner is absent or system-owned with zero data",
                "initialize post-owner is ChannelVault with 490-byte state",
                "vault post-owner is classic SPL Token",
                "modeled initialization failure preserves the complete pre-state",
            ],
            "result": "passed",
        },
    )
    write_json(
        "settlement-authority-report.json",
        {
            "authority": "PermissionlessBoundRecipientSettlement",
            "destination": "canonical_ata(bound_recipient_wallet, channel.mint)",
            "caller_identity_economic_effect": False,
            "obligation_hash": "caller_supplied_non_authoritative_correlation",
            "obligation_hash_economic_effect": False,
            "obligation_hash_business_outcome_proof": False,
            "property_test": "permissionless_settlement_is_caller_and_correlation_independent",
            "result": "passed",
        },
    )
    write_json(
        "validation-report.json",
        {
            "work_item": "FC-SOL-004",
            "baseline": args.baseline,
            "implementation_commit": args.implementation_commit,
            "model_operations": 8,
            "deterministic_tests": 4,
            "property_tests": 3,
            "property_cases": 1536,
            "bounded_exploration": bounded,
            "instruction_contract_tests": 16,
            "external_review": "not_performed",
            "formal_verification": "not_performed",
            "runtime_program_implemented": False,
            "deployment_authorization": {
                "pure_model": "allowed",
                "local_validator": "blocked",
                "devnet_fixture": "blocked",
                "mainnet": "blocked",
                "real_value": "blocked",
            },
            "claim": (
                "bounded transition exploration and property-based validation "
                "found no violation within the published model and bounds"
            ),
        },
    )
    write_json(
        "toolchain-report.json",
        {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "rustc": run([rustc(), PINNED_RUST_TOOLCHAIN, "--version"]).strip(),
            "cargo": run([cargo_bin, PINNED_RUST_TOOLCHAIN, "--version"]).strip(),
            "proptest": "1.6.0",
        },
    )

    artifacts = []
    source_paths = [
        ROOT / "programs/foundry-channel-vault/transition-model/src/lib.rs",
        ROOT / "programs/foundry-channel-vault/transition-model/examples/bounded_explorer.rs",
        ROOT / "programs/foundry-channel-vault/transition-model/Cargo.toml",
        ROOT / "programs/foundry-channel-vault/transition-model/Cargo.lock",
        ROOT / "programs/foundry-channel-vault/transition-model/rust-toolchain.toml",
        ROOT / "programs/foundry-channel-vault/instruction-contract/src/contract.rs",
        ROOT
        / "programs/foundry-channel-vault/instruction-contract/examples/generate_instruction_vectors.rs",
        ROOT / "docs/channels/solana/invariants/FC-SOL-004-CONTRACT.md",
        ROOT / "tests/channels/solana/invariants/test_fc_sol_004.py",
        *sorted(path for path in EVIDENCE.iterdir() if path.is_file()),
    ]
    for path in source_paths:
        if path.name == "artifact-manifest.json":
            continue
        artifacts.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_json(
        "artifact-manifest.json",
        {
            "work_item": "FC-SOL-004",
            "baseline": args.baseline,
            "implementation_commit": args.implementation_commit,
            "artifacts": artifacts,
        },
    )


if __name__ == "__main__":
    main()
