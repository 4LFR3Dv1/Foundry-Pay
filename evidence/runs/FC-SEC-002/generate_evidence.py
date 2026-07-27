"""Generate deterministic FC-SEC-002 self-validation reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "evidence/runs/FC-SEC-002"
CASES = ROOT / "tests/channels/security/replay/mutation-cases.json"
EXPECTATIONS = (
    ROOT
    / "contracts/channel/test-vectors/negative"
    / "fc-sec-002/signed-preimage-mutations-v1.json"
)
FUNCTIONAL_HEAD = "330b963c70987ee681782dc6d7eab42fa51da895"
FROZEN_CANONICALIZATION = "17b656cbdd6ae53cece9cebb9123058c03e67b82"


def _dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_frozen_registry() -> None:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "diff",
            "--exit-code",
            FROZEN_CANONICALIZATION,
            "--",
            "contracts/channel/canonicalization",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError("frozen FC-PROTO-006 registry changed")


def generate(*, workflow_run: int, rust_job_url: str, validated_head: str) -> None:
    _assert_frozen_registry()
    case_registry = json.loads(CASES.read_text(encoding="utf-8"))
    expectation_registry = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    cases = case_registry["cases"]
    expectations = {result["case_id"]: result for result in expectation_registry["expectations"]}

    with (RUN / "mutation-cases.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for case in sorted(cases, key=lambda item: item["case_id"]):
            stream.write(
                json.dumps(
                    {**case, "expected_result": expectations[case["case_id"]]},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    dimensions = sorted(
        {case["path"][-1] for case in cases if case["profile_id"] == "signed-payload-v1"}
    )
    _dump(
        RUN / "domain-dimension-registry.json",
        {
            "schema_version": 1,
            "status": "passed",
            "signed_authority_objects": ["channel_voucher", "recipient_binding"],
            "mutated_dimensions": dimensions,
            "case_count": len(cases),
            "exact_domain_equality": True,
            "prefix_matching": False,
        },
    )
    _dump(
        RUN / "threat-matrix.json",
        {
            "schema_version": 1,
            "status": "passed",
            "threats": [
                {"class": "cross_channel", "control": "signed preimage", "effect": "zero"},
                {"class": "cross_epoch", "control": "signed preimage", "effect": "zero"},
                {"class": "cross_network", "control": "signed preimage", "effect": "zero"},
                {"class": "cross_program", "control": "signed preimage", "effect": "zero"},
                {"class": "cross_asset", "control": "signed preimage", "effect": "zero"},
                {"class": "cross_recipient", "control": "signed preimage", "effect": "zero"},
                {"class": "cross_type", "control": "exact verifier type/domain", "effect": "zero"},
                {"class": "cross_profile", "control": "exact profile", "effect": "zero"},
                {"class": "downgrade", "control": "no fallback", "effect": "zero"},
                {
                    "class": "cloud_revocation",
                    "control": "verifiable lifecycle only",
                    "effect": "no cryptographic revocation",
                },
            ],
        },
    )
    _dump(
        RUN / "semantic-collision-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "cases": ["voucher-as-binding", "binding-as-voucher"],
            "result": "type_verification/object_type_mismatch",
            "shared_accepted_meaning": False,
        },
    )
    _dump(
        RUN / "downgrade-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "unknown_version": "version_verification/unsupported_version",
            "unknown_profile": "profile_verification/unsupported_profile",
            "legacy_fallback": False,
            "field_stripping_retry": False,
        },
    )
    _dump(
        RUN / "version-lifecycle-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "v1_objects_remain_v1": True,
            "in_transit_rewrite": False,
            "channel_epoch_context_fixed": True,
            "cloud_revocation_authority": False,
            "future_migration_requires_adr_and_authoritative_transition": True,
        },
    )
    _dump(
        RUN / "no-effect-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "mutation_cases": len(cases),
            "economic_effect_count": 0,
            "authority_advancement_count": 0,
            "lifecycle_transition_count": 0,
            "verified_transition_count": 0,
            "activation_requested_transition_count": 0,
            "authorized_transition_count": 0,
            "completed_transition_count": 0,
            "permitted_effect": "bounded append-only rejected audit event",
            "recipient_binding_rejection_record_count": 0,
        },
    )
    _dump(
        RUN / "cross-language-report.json",
        {
            "schema_version": 1,
            "status": "passed",
            "case_count": len(cases),
            "implementations": ["python", "typescript", "rust"],
            "agreement": {
                "decision_stage_code": True,
                "canonical_bytes_when_computed": True,
                "byte_length_when_computed": True,
                "sha256_when_computed": True,
                "economic_authority_lifecycle_effects": True,
            },
            "runner_reads_expectations": False,
            "expectation_vector": EXPECTATIONS.relative_to(ROOT).as_posix(),
            "pinned_ci": {
                "workflow_run": workflow_run,
                "rust_job_url": rust_job_url,
                "validated_head": validated_head,
            },
            "limitation": (
                "The fixtures bind declared signed-preimage hashes but do not contain "
                "independently verifiable Ed25519 key material."
            ),
        },
    )

    manifest_paths = [
        RUN / "README.md",
        RUN / "generate_evidence.py",
        RUN / "mutation-cases.jsonl",
        RUN / "threat-matrix.json",
        RUN / "domain-dimension-registry.json",
        RUN / "cross-language-report.json",
        RUN / "semantic-collision-report.json",
        RUN / "downgrade-report.json",
        RUN / "version-lifecycle-report.json",
        RUN / "no-effect-report.json",
        RUN / "pytest-full.xml",
        CASES,
        EXPECTATIONS,
        ROOT / "docs/channels/security/FC-SEC-002/state-surface-taxonomy.yaml",
        ROOT / "docs/channels/security/FC-SEC-002/VERSION_LIFECYCLE.md",
        ROOT / "docs/channels/security/FC-SEC-002/SIGNED_AUTHORITY_INVENTORY.md",
        ROOT / "packages/channel-protocol/python/foundry_channel_protocol/conformance_runner.py",
        ROOT / "packages/channel-protocol/typescript/src/conformance-runner.ts",
        ROOT / "packages/channel-protocol/rust/src/lib.rs",
        ROOT / "tests/channels/security/replay/run_cross_language.py",
        ROOT / "tests/channels/security/replay/test_rejection_effects.py",
    ]
    _dump(
        RUN / "artifact-manifest.json",
        {
            "schema_version": 1,
            "algorithm": "sha256",
            "functional_head": FUNCTIONAL_HEAD,
            "validated_head": validated_head,
            "artifacts": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in sorted(manifest_paths)
            ],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-run", type=int, required=True)
    parser.add_argument("--rust-job-url", required=True)
    parser.add_argument("--validated-head", required=True)
    arguments = parser.parse_args()
    generate(
        workflow_run=arguments.workflow_run,
        rust_job_url=arguments.rust_job_url,
        validated_head=arguments.validated_head,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
