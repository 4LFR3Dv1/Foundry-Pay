"""Validate the Foundry Channels design contracts and foundation gates."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).parents[1]
CONTRACTS = ROOT / "contracts" / "channel"
POSITIVE = CONTRACTS / "test-vectors" / "positive" / "cumulative-channel-v1.json"
POSITIVE_CLOSE = CONTRACTS / "test-vectors" / "positive" / "close-race-v1.json"
NEGATIVE = CONTRACTS / "test-vectors" / "negative"
WORK_ITEMS = ROOT / "docs" / "channels" / "work-items.yaml"

SCHEMAS = (
    "channel.schema.json",
    "channel-voucher.schema.json",
    "recipient-binding.schema.json",
    "channel-claim.schema.json",
    "settlement.schema.json",
    "channel-closure.schema.json",
    "channel-evidence.schema.json",
)

REQUIRED_DOCS = (
    "PROGRAM.md",
    "ARCHITECTURE.md",
    "PRODUCT_THESIS.md",
    "REPO_BOUNDARIES.md",
    "WORK_GRAPH.md",
    "DECISIONS.md",
    "EVIDENCE_INDEX.md",
    "CHANNEL_PROTOCOL.md",
    "VOUCHER_MODEL.md",
    "STATE_MACHINES.md",
    "THREAT_MODEL.md",
    "AUTHORITY_MODEL.md",
    "FAILURE_AND_RECOVERY.md",
    "MVP_VERTICAL_SLICE.md",
    "PRODUCT_EXPERIENCE.md",
    "OPEN_QUESTIONS.md",
    "GLOSSARY.md",
    "SECURITY_GATES.md",
)

REQUIRED_ADRS = tuple(
    f"FC-ADR-{number:03d}-{name}.md"
    for number, name in (
        (1, "channel-primitive"),
        (2, "onchain-offchain-state"),
        (3, "public-private-boundary"),
        (4, "link-and-recipient-binding"),
        (5, "repository-topology"),
    )
)

REQUIRED_WORK_ITEMS = {
    *(f"FC-CTRL-{number:03d}" for number in range(1, 7)),
    *(f"FC-PROTO-{number:03d}" for number in range(1, 8)),
    *(f"FC-SEC-{number:03d}" for number in range(1, 6)),
    *(f"FC-SOL-{number:03d}" for number in range(1, 6)),
    *(f"SA-CHAN-{number:03d}" for number in range(1, 6)),
    *(f"FC-PROD-{number:03d}" for number in range(1, 7)),
    *(f"FC-VAL-{number:03d}" for number in range(1, 6)),
    "SA-CHAN-000",
    "FC-FAIL-003",
}

WORK_ITEM_FIELDS = {
    "status",
    "objective",
    "owner",
    "repository",
    "allowed_paths",
    "dependencies",
    "invariants",
    "acceptance",
    "tests",
    "evidence",
    "security_review",
    "stop_conditions",
}


def canonical_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def set_path(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    cursor: dict[str, Any] = target
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        child = cursor[part]
        if not isinstance(child, dict):
            raise TypeError(f"{dotted_path}: {part} is not an object")
        cursor = child
    cursor[parts[-1]] = value


def semantic_error(vector: dict[str, Any]) -> str | None:
    channel = vector["channel_after_funding"]
    policy = vector["channel_policy"]
    vouchers = vector["vouchers"]
    binding = vector["recipient_binding"]
    request = vector["settlement_request"]
    constants = vector["constants"]

    previous_sequence = 0
    previous_amount = 0
    previous_hash = constants["genesis_voucher_hash"]
    funded = int(channel["funded_total_base_units"])
    policy_limit = int(policy["max_cumulative_authorized_base_units"])

    for voucher in vouchers:
        payload = voucher["payload"]
        if payload["network"] != constants["network"]:
            return "network_mismatch"
        if payload["channel_id"] != constants["channel_id"]:
            return "channel_mismatch"
        if payload["mint"] != constants["mint"]:
            return "mint_mismatch"
        if payload["sequence"] <= previous_sequence:
            return "sequence_not_monotonic"
        amount = int(payload["cumulative_authorized_base_units"])
        if amount < previous_amount:
            return "cumulative_amount_decreased"
        if amount > funded or amount > policy_limit:
            return "authorization_exceeds_funding"
        if payload["previous_activated_voucher_hash"] != previous_hash:
            return "previous_voucher_hash_mismatch"
        if parse_time(payload["expires_at"]) < parse_time(request["requested_at"]):
            return "voucher_expired"
        if canonical_hash(payload) != voucher["voucher_hash"]:
            return "voucher_hash_mismatch"
        previous_sequence = payload["sequence"]
        previous_amount = amount
        previous_hash = voucher["voucher_hash"]

    binding_payload = binding["payload"]
    if binding_payload["binding_nonce"] < 1:
        return "binding_nonce_not_monotonic"
    if canonical_hash(binding_payload) != binding["binding_hash"]:
        return "binding_hash_mismatch"
    if binding_payload["channel_id"] != constants["channel_id"]:
        return "binding_channel_mismatch"
    if binding_payload["destination_wallet"] != constants["recipient_wallet"]:
        return "destination_mismatch"

    if request["voucher_hash"] != previous_hash:
        return "settlement_voucher_hash_mismatch"
    before = int(request["settled_total_before_base_units"])
    requested = int(request["requested_amount_base_units"])
    after = int(request["settled_total_after_base_units"])
    activated = int(request["activated_authorized_total_base_units"])
    if after != before + requested:
        return "settlement_total_mismatch"
    if after > activated or activated > funded:
        return "settlement_exceeds_authorized"
    if request["recipient_wallet"] != binding_payload["destination_wallet"]:
        return "settlement_destination_mismatch"
    return None


def mutated_vector(base: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(base)
    target_name = case["target"]
    if target_name.startswith("voucher:"):
        index = int(target_name.split(":", maxsplit=1)[1]) - 1
        target = candidate["vouchers"][index]
    else:
        target = candidate[target_name]
    set_path(target, case["mutation"]["path"], case["mutation"]["value"])
    return candidate


def parse_work_items(path: Path) -> dict[str, dict[str, str]]:
    """Parse only the stable top-level shape of our YAML without adding a dependency."""
    items: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    current_id: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("  - id: "):
            current_id = raw_line.removeprefix("  - id: ").strip()
            current = {}
            items[current_id] = current
        elif current is not None and raw_line.startswith("    ") and ":" in raw_line:
            key, value = raw_line.strip().split(":", maxsplit=1)
            if key in WORK_ITEM_FIELDS:
                current[key] = value.strip()
    return items


def validate() -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    schemas: dict[str, dict[str, Any]] = {}

    for name in SCHEMAS:
        schema = json.loads((CONTRACTS / name).read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # pragma: no cover - defensive reporting
            errors.append(f"schema {name}: {exc}")
        schemas[name] = schema
    checks["schemas"] = {"count": len(schemas), "valid": not errors}

    vector = json.loads(POSITIVE.read_text(encoding="utf-8"))
    schema_targets = (
        ("channel_policy", "channel.schema.json"),
        ("channel_after_funding", "channel.schema.json"),
        ("funding", "channel.schema.json"),
        ("recipient_binding", "recipient-binding.schema.json"),
        ("claim", "channel-claim.schema.json"),
        ("settlement_request", "settlement.schema.json"),
    )
    format_checker = FormatChecker()
    for key, schema_name in schema_targets:
        validator = Draft202012Validator(schemas[schema_name], format_checker=format_checker)
        for error in validator.iter_errors(vector[key]):
            errors.append(f"positive {key}: {error.message}")
    voucher_validator = Draft202012Validator(
        schemas["channel-voucher.schema.json"], format_checker=format_checker
    )
    for index, voucher in enumerate(vector["vouchers"], start=1):
        for error in voucher_validator.iter_errors(voucher):
            errors.append(f"positive voucher {index}: {error.message}")
    positive_semantic_error = semantic_error(vector)
    if positive_semantic_error:
        errors.append(f"positive semantic validation: {positive_semantic_error}")
    checks["positive_vector"] = {
        "scenario": vector["scenario"],
        "voucher_hashes": [voucher["voucher_hash"] for voucher in vector["vouchers"]],
        "binding_hash": vector["recipient_binding"]["binding_hash"],
        "valid": positive_semantic_error is None,
    }

    close_vector = json.loads(POSITIVE_CLOSE.read_text(encoding="utf-8"))
    closure = close_vector["closure_request"]
    closure_validator = Draft202012Validator(
        schemas["channel-closure.schema.json"], format_checker=format_checker
    )
    closure_schema_errors = list(closure_validator.iter_errors(closure))
    errors.extend(f"close-race closure: {error.message}" for error in closure_schema_errors)
    held = close_vector["voucher_held_at_close"]
    during = close_vector["expected_during_claim_window"]
    after = close_vector["expected_after_settlement_and_deadline"]
    close_rule_checks = {
        "deadline_matches_activation_window": (
            closure["activation_allowed_until"] == closure["claim_deadline"]
        ),
        "presentation_is_inside_window": (
            parse_time(closure["requested_at"])
            < parse_time(held["presented_at"])
            < parse_time(closure["claim_deadline"])
        ),
        "voucher_advances_snapshot": (
            held["sequence"] > closure["latest_activated_sequence_at_request"]
            and held["previous_activated_voucher_hash"]
            == closure["latest_activated_voucher_hash_at_request"]
        ),
        "pre_deadline_refund_is_zero": (
            closure["pre_deadline_refundable_base_units"] == "0"
            and during["pre_deadline_refund"] == "rejected"
            and during["pre_deadline_refundable_base_units"] == "0"
        ),
        "valid_voucher_activates_during_window": (
            held["sender_signature_present"]
            and during["activation"] == "accepted"
            and during["activated_authorized_total_base_units"]
            == held["cumulative_authorized_base_units"]
        ),
        "post_deadline_conservation": (
            int(after["settled_total_base_units"]) + int(after["vault_balance_base_units"])
            == 100_000_000
            and after["post_deadline_refundable_base_units"] == after["vault_balance_base_units"]
            and after["activation_after_deadline"] == "rejected"
        ),
    }
    failed_close_rules = [name for name, passed in close_rule_checks.items() if not passed]
    errors.extend(f"close-race rule failed: {name}" for name in failed_close_rules)
    checks["closing_race_vector"] = {
        "scenario": close_vector["scenario"],
        "schema_valid": not closure_schema_errors,
        "rules": close_rule_checks,
        "valid": not closure_schema_errors and not failed_close_rules,
    }

    negative_results = []
    for path in sorted(NEGATIVE.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        observed = semantic_error(mutated_vector(vector, case))
        passed = observed == case["expected_error"]
        if not passed:
            errors.append(
                f"negative {case['case_id']}: expected {case['expected_error']}, got {observed}"
            )
        negative_results.append(
            {
                "case_id": case["case_id"],
                "expected_error": case["expected_error"],
                "observed_error": observed,
                "passed": passed,
            }
        )
    checks["negative_vectors"] = {
        "count": len(negative_results),
        "results": negative_results,
    }

    docs_root = ROOT / "docs" / "channels"
    missing_docs = [name for name in REQUIRED_DOCS if not (docs_root / name).is_file()]
    missing_adrs = [name for name in REQUIRED_ADRS if not (docs_root / "ADR" / name).is_file()]
    errors.extend(f"missing document: {name}" for name in missing_docs)
    errors.extend(f"missing ADR: {name}" for name in missing_adrs)
    checks["documents"] = {
        "required": len(REQUIRED_DOCS) + len(REQUIRED_ADRS),
        "missing": missing_docs + missing_adrs,
    }

    work_items = parse_work_items(WORK_ITEMS)
    missing_items = sorted(REQUIRED_WORK_ITEMS - work_items.keys())
    incomplete_items = {
        item_id: sorted(WORK_ITEM_FIELDS - fields.keys())
        for item_id, fields in work_items.items()
        if WORK_ITEM_FIELDS - fields.keys()
    }
    ready_items = sorted(
        item_id for item_id, fields in work_items.items() if fields.get("status") == "ready"
    )
    done_items = {
        item_id for item_id, fields in work_items.items() if fields.get("status") == "done"
    }
    invalid_statuses = {
        item_id: fields.get("status")
        for item_id, fields in work_items.items()
        if fields.get("status") not in {"blocked", "ready", "active", "review", "done"}
    }
    ready_with_incomplete_dependencies: dict[str, list[str]] = {}
    for item_id in ready_items:
        dependencies = work_items[item_id].get("dependencies", "")
        dependency_ids = [
            value.strip()
            for value in dependencies.removeprefix("[").removesuffix("]").split(",")
            if value.strip() and value.strip() != "FOUNDATIONS-001"
        ]
        incomplete = sorted(
            dependency for dependency in dependency_ids if dependency not in done_items
        )
        if incomplete:
            ready_with_incomplete_dependencies[item_id] = incomplete
    if missing_items:
        errors.append(f"missing work items: {', '.join(missing_items)}")
    if incomplete_items:
        errors.append(f"incomplete work items: {json.dumps(incomplete_items, sort_keys=True)}")
    if invalid_statuses:
        errors.append(f"invalid work-item statuses: {json.dumps(invalid_statuses, sort_keys=True)}")
    if ready_with_incomplete_dependencies:
        errors.append(
            "ready work items have incomplete dependencies: "
            + json.dumps(ready_with_incomplete_dependencies, sort_keys=True)
        )
    checks["work_graph"] = {
        "required_item_count": len(REQUIRED_WORK_ITEMS),
        "observed_item_count": len(work_items),
        "missing_items": missing_items,
        "incomplete_items": incomplete_items,
        "ready_items": ready_items,
        "invalid_statuses": invalid_statuses,
        "ready_with_incomplete_dependencies": ready_with_incomplete_dependencies,
    }

    final = vector["expected_final_state"]
    funded = int(final["funded_total_base_units"])
    vault = int(final["vault_balance_base_units"])
    settled = int(final["settled_total_base_units"])
    refunded = int(final["refunded_total_base_units"])
    activated = int(final["activated_authorized_total_base_units"])
    conservation = funded == vault + settled + refunded
    rights = 0 <= settled <= activated <= funded - refunded
    if not conservation:
        errors.append("final state violates F = V + S + R")
    if not rights:
        errors.append("final state violates 0 <= S <= A <= F - R")
    checks["accounting"] = {"conservation": conservation, "rights_bounds": rights}

    return {
        "check": "FOUNDATIONS-001",
        "status": "passed" if not errors else "failed",
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
