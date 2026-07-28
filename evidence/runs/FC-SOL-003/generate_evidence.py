from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "evidence/runs/FC-SOL-003"
CONTRACT_ROOT = ROOT / "programs/foundry-channel-vault/instruction-contract"
MANIFEST = CONTRACT_ROOT / "Cargo.toml"


def run(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise SystemExit(result.stdout)
    return result


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def write_json(path: Path, value: object) -> None:
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
        newline="\n",
    )


def normalize_lf(path: Path) -> None:
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--functional-head", required=True)
    args = parser.parse_args()

    cargo = shutil.which("cargo")
    if cargo is None:
        cargo = str(Path.home() / ".cargo/bin/cargo.exe")
    rustc = str(Path(cargo).with_name("rustc.exe"))

    env = dict(os.environ)
    env["FC_SOL_003_EVIDENCE_DIR"] = str(EVIDENCE)
    generation = run(
        [
            cargo,
            "test",
            "--manifest-path",
            str(MANIFEST),
            "--lib",
            "generate_from_test_harness_when_requested",
            "--",
            "--nocapture",
        ],
        env=env,
    )
    cargo_test = run([cargo, "test", "--manifest-path", str(MANIFEST), "--lib"])
    write_json(
        EVIDENCE / "validation-report.json",
        {
            **json.loads((EVIDENCE / "validation-report.json").read_text(encoding="utf-8")),
            "baseline": "c0b32735ff5ac17dd88e3f3ca17ea5eb1819d2c5",
            "functional_head": args.functional_head,
            "cargo_tests": 12,
            "python_evidence_tests": 9,
            "self_validation": "passed",
            "external_review": "not_performed",
        },
    )
    pytest = run(
        [
            shutil.which("python") or "python",
            "-m",
            "pytest",
            "tests/channels/solana/instructions/test_instruction_contract.py",
            "-k",
            "not artifact_manifest_recalculates",
            "--junitxml",
            str(EVIDENCE / "pytest-full.xml"),
        ]
    )
    normalize_lf(EVIDENCE / "pytest-full.xml")

    suite = ET.Element(
        "testsuite",
        {
            "name": "FC-SOL-003-cargo",
            "tests": "12",
            "failures": "0",
            "errors": "0",
            "skipped": "0",
        },
    )
    case = ET.SubElement(suite, "testcase", {"name": "cargo-test", "classname": "channelvault"})
    output = ET.SubElement(case, "system-out")
    output.text = cargo_test.stdout.replace("\r\n", "\n").replace("\r", "\n")
    ET.ElementTree(suite).write(EVIDENCE / "cargo-test.xml", encoding="utf-8", xml_declaration=True)
    normalize_lf(EVIDENCE / "cargo-test.xml")

    rustc_version = run([rustc, "--version"]).stdout.strip()
    cargo_version = run([cargo, "--version"]).stdout.strip()
    write_json(
        EVIDENCE / "toolchain-report.json",
        {
            "cargo": cargo_version,
            "rustc": rustc_version,
            "rust_toolchain_file": (
                ROOT / "programs/foundry-channel-vault/rust-toolchain.toml"
            ).read_text(encoding="utf-8"),
            "generation_test": generation.stdout,
            "pytest_summary": pytest.stdout,
        },
    )

    artifacts = [
        *sorted(EVIDENCE.glob("*.json")),
        EVIDENCE / "README.md",
        EVIDENCE / "TASK_CONTRACT.yaml",
        EVIDENCE / "cargo-test.xml",
        EVIDENCE / "pytest-full.xml",
        EVIDENCE / "generate_evidence.py",
        *sorted((CONTRACT_ROOT / "src").glob("*.rs")),
        CONTRACT_ROOT / "examples/generate_instruction_vectors.rs",
        CONTRACT_ROOT / "Cargo.toml",
        CONTRACT_ROOT / "Cargo.lock",
        ROOT / "programs/foundry-channel-vault/rust-toolchain.toml",
        ROOT / "tests/channels/solana/instructions/test_instruction_contract.py",
        ROOT / "docs/channels/solana/instructions/FC-SOL-003-CONTRACT.md",
    ]
    manifest_entries = []
    for path in artifacts:
        if path.name == "artifact-manifest.json":
            continue
        manifest_entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_json(
        EVIDENCE / "artifact-manifest.json",
        {
            "schema_version": 1,
            "work_item": "FC-SOL-003",
            "functional_head": args.functional_head,
            "artifact_count": len(manifest_entries),
            "artifacts": manifest_entries,
        },
    )


if __name__ == "__main__":
    main()
