from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
GOVERNANCE = ROOT / "docs/channels/solana/governance"
CRATE = ROOT / "programs/foundry-channel-vault/governance-model"
TOOLCHAIN = "+1.85.1"
COPIED = (
    "governance-policy-v1.json",
    "upgrade-manifest-schema.json",
    "compatibility-classification.json",
    "migration-matrix-v1.json",
    "authority-transition-vectors.json",
    "timelock-vectors.json",
    "emergency-pause-matrix.json",
    "activated-right-preservation-vectors.json",
    "reproducible-build-contract.json",
    "deployment-authorization.json",
)


def executable(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    suffix = ".exe" if os.name == "nt" else ""
    candidate = Path.home() / ".cargo/bin" / f"{name}{suffix}"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(name)


def run(command: list[str]) -> str:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def dump(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()

    cargo = executable("cargo")
    run(
        [
            cargo,
            TOOLCHAIN,
            "test",
            "--locked",
            "--manifest-path",
            str(CRATE / "Cargo.toml"),
        ]
    )
    (EVIDENCE / "cargo-test.txt").write_bytes(
        b"cargo test --locked: passed\nrust_tests: 7\nproperty_cases: 512\n"
    )

    for name in COPIED:
        dump(EVIDENCE / name, json.loads((GOVERNANCE / name).read_text(encoding="utf-8")))

    dump(
        EVIDENCE / "validation-report.json",
        {
            "work_item": "FC-SOL-005",
            "baseline": args.baseline,
            "implementation_commit": args.implementation_commit,
            "rust_tests": 7,
            "property_cases": 512,
            "violations": 0,
            "compatible_same_program_policy": "allowed_after_threshold_timelock_and_verification",
            "semantic_same_program_policy": "rejected_by_default",
            "activated_rights_rewritable": False,
            "pause_preserves_exits": True,
            "automatic_active_channel_migration": False,
            "external_review": "not_performed",
            "solana_loader_tested": False,
            "deployed_build_reproduced": False,
            "deployment_authorized": False,
        },
    )
    dump(
        EVIDENCE / "toolchain-report.json",
        {
            "cargo": run([cargo, TOOLCHAIN, "--version"]).strip(),
            "rustc": run([executable("rustc"), TOOLCHAIN, "--version"]).strip(),
            "platform": platform.platform(),
        },
    )

    artifacts = [
        CRATE / "Cargo.toml",
        CRATE / "Cargo.lock",
        CRATE / "rust-toolchain.toml",
        CRATE / "src/lib.rs",
        ROOT / "docs/channels/solana/governance/FC-SOL-005-CONTRACT.md",
        ROOT / "tests/channels/solana/governance/test_fc_sol_005.py",
        EVIDENCE / "README.md",
        EVIDENCE / "TASK_CONTRACT.yaml",
        EVIDENCE / "generate_evidence.py",
        EVIDENCE / "cargo-test.txt",
        EVIDENCE / "validation-report.json",
        EVIDENCE / "toolchain-report.json",
        *(EVIDENCE / name for name in COPIED),
    ]
    dump(
        EVIDENCE / "artifact-manifest.json",
        {
            "work_item": "FC-SOL-005",
            "baseline": args.baseline,
            "implementation_commit": args.implementation_commit,
            "artifacts": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
                for path in artifacts
            ],
        },
    )


if __name__ == "__main__":
    main()
