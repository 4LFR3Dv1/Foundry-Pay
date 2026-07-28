from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).parents[3]
EVIDENCE = Path(__file__).parent
MANIFEST = ROOT / "programs/foundry-channel-vault/Cargo.toml"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def write_json(name: str, value: object) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    baseline = "beef6708ea7e21d07dcc4b693e22a8de1358e3e2"
    functional_head = run(["git", "rev-parse", "HEAD"]).stdout.strip()

    task = yaml.safe_load((ROOT / ".agents/tasks/FC-SOL-002.yaml").read_text("utf-8"))
    (EVIDENCE / "TASK_CONTRACT.yaml").write_text(
        yaml.safe_dump(task, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    cargo_test = run(["cargo", "test", "--manifest-path", str(MANIFEST)])
    testsuite = ET.Element(
        "testsuite",
        name="FC-SOL-002-cargo",
        tests="1",
        failures="0" if cargo_test.returncode == 0 else "1",
    )
    testcase = ET.SubElement(testsuite, "testcase", name="cargo-test")
    if cargo_test.returncode != 0:
        failure = ET.SubElement(testcase, "failure", message="cargo test failed")
        failure.text = cargo_test.stdout + cargo_test.stderr
    ET.ElementTree(testsuite).write(
        EVIDENCE / "cargo-test.xml",
        encoding="utf-8",
        xml_declaration=True,
    )
    if cargo_test.returncode != 0:
        return cargo_test.returncode

    generated = run(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(MANIFEST),
            "--example",
            "generate_vectors",
            "--",
            str(EVIDENCE),
        ]
    )
    if generated.returncode != 0:
        sys.stderr.write(generated.stdout + generated.stderr)
        return generated.returncode

    rustc = run(["rustc", "--version"]).stdout.strip()
    cargo = run(["cargo", "--version"]).stdout.strip()
    write_json(
        "toolchain-report.json",
        {
            "rustc": rustc,
            "cargo": cargo,
            "solana_pubkey": "2.1.21",
            "solana_rent": "2.1.21",
            "python": sys.version.split()[0],
            "solders": __import__("solders").__version__,
            "environment": "local-validator-compatible account model; no deployment",
        },
    )

    write_json(
        "validation-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "work_item": "FC-SOL-002",
            "baseline": baseline,
            "functional_head": functional_head,
            "claim": (
                "versioned fixed-width account model, deterministic PDA derivation, "
                "classic SPL Token vault boundary, and local-only golden vectors"
            ),
            "external_review": "not_performed",
            "deployment_authorization": {
                "local_validator": "allowed",
                "devnet_fixture": "blocked",
                "mainnet": "blocked",
                "real_value": "blocked",
            },
            "instructions_implemented": False,
            "cpi_implemented": False,
            "token_transfers_implemented": False,
            "ed25519_implemented": False,
        },
    )

    files = [
        *sorted(EVIDENCE.glob("*.json")),
        EVIDENCE / "TASK_CONTRACT.yaml",
        EVIDENCE / "cargo-test.xml",
        *sorted((ROOT / "programs/foundry-channel-vault/src").glob("*.rs")),
        *sorted((ROOT / "programs/foundry-channel-vault/examples").glob("*.rs")),
        *sorted((ROOT / "tests/channels/solana/accounts").glob("*.py")),
        ROOT / "programs/foundry-channel-vault/Cargo.toml",
        ROOT / "programs/foundry-channel-vault/Cargo.lock",
        EVIDENCE / "generate_evidence.py",
    ]
    manifest = {
        "schema_version": 1,
        "baseline": baseline,
        "functional_head": functional_head,
        "artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "byte_length": path.stat().st_size,
                "sha256": f"sha256:{sha256(path)}",
            }
            for path in files
            if path.name != "artifact-manifest.json"
        ],
    }
    write_json("artifact-manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
