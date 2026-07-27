"""Run the three independent signed-preimage mutation verifiers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
REGISTRY = ROOT / "contracts/channel/canonicalization"
CASES = Path(__file__).with_name("mutation-cases.json")
CHANNEL_PYTHON = ROOT / "packages/channel-protocol/python"
CHANNEL_TYPESCRIPT = ROOT / "packages/channel-protocol/typescript"
CHANNEL_RUST = ROOT / "packages/channel-protocol/rust"
IMPLEMENTATIONS = ("python", "typescript", "rust")
COMMON_FIELDS = (
    "case_id",
    "decision",
    "stage",
    "code",
    "economic_effect_count",
    "authority_advancement_count",
    "lifecycle_transition_count",
    "verified_transition_count",
    "activation_requested_transition_count",
    "authorized_transition_count",
    "completed_transition_count",
    "mutated_canonical_utf8_hex",
    "mutated_byte_length",
    "mutated_sha256",
)


def _run(command: list[str], *, environment: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr}"
        )
    return completed.stdout


def _commands() -> dict[str, tuple[list[str], dict[str, str] | None]]:
    python_environment = os.environ.copy()
    existing = python_environment.get("PYTHONPATH")
    python_environment["PYTHONPATH"] = str(CHANNEL_PYTHON) + (
        os.pathsep + existing if existing else ""
    )
    common = ["--registry-root", str(REGISTRY), "--security-cases", str(CASES)]
    return {
        "python": (
            [sys.executable, "-m", "foundry_channel_protocol.conformance_runner", *common],
            python_environment,
        ),
        "typescript": (
            [
                "node",
                str(
                    CHANNEL_TYPESCRIPT
                    / "dist/packages/channel-protocol/typescript/src/conformance-runner.js"
                ),
                *common,
            ],
            None,
        ),
        "rust": (
            [
                "cargo",
                "run",
                "--quiet",
                "--locked",
                "--manifest-path",
                str(CHANNEL_RUST / "Cargo.toml"),
                "--",
                *common,
            ],
            None,
        ),
    }


def _load_stream(value: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in value.splitlines() if line]


def run(output_root: Path | None = None) -> dict[str, Any]:
    streams: dict[str, list[dict[str, Any]]] = {}
    for implementation, (command, environment) in _commands().items():
        raw = _run(command, environment=environment)
        streams[implementation] = _load_stream(raw)
        if output_root is not None:
            output_root.mkdir(parents=True, exist_ok=True)
            (output_root / f"{implementation}-results.jsonl").write_text(
                raw,
                encoding="utf-8",
                newline="\n",
            )

    expected_ids = [result["case_id"] for result in streams["python"]]
    if len(expected_ids) != 23 or expected_ids != sorted(expected_ids):
        raise RuntimeError("expected 23 sorted mutation cases")
    for implementation in IMPLEMENTATIONS:
        actual_ids = [result["case_id"] for result in streams[implementation]]
        if actual_ids != expected_ids:
            raise RuntimeError(f"{implementation} emitted a different case set")

    for index, case_id in enumerate(expected_ids):
        reference = streams["python"][index]
        for implementation in IMPLEMENTATIONS:
            result = streams[implementation][index]
            for field in COMMON_FIELDS:
                if result.get(field) != reference.get(field):
                    raise RuntimeError(
                        f"{case_id}: {implementation} differs on {field}: "
                        f"{result.get(field)!r} != {reference.get(field)!r}"
                    )
            if result["decision"] != "reject":
                raise RuntimeError(f"{case_id}: mutation was not rejected")
            for field in (
                "economic_effect_count",
                "authority_advancement_count",
                "lifecycle_transition_count",
                "verified_transition_count",
                "activation_requested_transition_count",
                "authorized_transition_count",
                "completed_transition_count",
            ):
                if result[field] != 0:
                    raise RuntimeError(f"{case_id}: forbidden effect in {implementation}")

    return {
        "schema_version": 1,
        "status": "passed",
        "runner_contract": "foundry.channels.security-mutation-result/1",
        "case_count": len(expected_ids),
        "implementations": list(IMPLEMENTATIONS),
        "agreement_fields": list(COMMON_FIELDS),
        "all_rejected": True,
        "economic_effect_count": 0,
        "authority_advancement_count": 0,
        "lifecycle_transition_count": 0,
        "limitation": (
            "Fixtures bind declared signed-preimage hashes but do not contain "
            "independently verifiable Ed25519 key material."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    arguments = parser.parse_args()
    try:
        report = run(arguments.output_root)
    except Exception as error:
        print(f"security mutation conformance failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
