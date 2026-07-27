"""Generate reviewed FC-SEC-002 expectations from the frozen Python projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(ROOT / "packages/channel-protocol/python"))

from foundry_channel_protocol.conformance_runner import run_security_cases  # noqa: E402


CASES = Path(__file__).with_name("mutation-cases.json")
REGISTRY = ROOT / "contracts/channel/canonicalization"
DESTINATION = (
    ROOT
    / "contracts/channel/test-vectors/negative"
    / "fc-sec-002-signed-preimage-mutations-v1.json"
)
FIELDS = (
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


def main() -> int:
    results = run_security_cases(CASES, REGISTRY)
    value = {
        "schema_version": 1,
        "vector_set": "foundry.channels.fc-sec-002.signed-preimage-mutations",
        "version": "1.0.0",
        "source_registry": "contracts/channel/canonicalization",
        "source_cases": "tests/channels/security/replay/mutation-cases.json",
        "generator_implementation": "python",
        "runner_dependency": "foundry.channels.security-mutation-result/1",
        "runner_reads_expectations": False,
        "expectations": [
            {field: result[field] for field in FIELDS if field in result} for result in results
        ],
    }
    DESTINATION.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
