"""Validate version-bound Foundry Channels maturity and authorization records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).parents[1]
SCHEMA_PATH = ROOT / "contracts/governance/component-maturity.schema.json"
HIGH_RISK_AUTHORIZATIONS = ("mainnet", "real_value")
EXPERIMENTAL_AUTHORIZATIONS = ("local_validator", "devnet_fixture")


def schema_errors(record: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(part) for part in error.path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path))
    ]


def semantic_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    current_commit = record["current_commit"]
    maturity = record["maturity"]
    self_validation = maturity["self_validation"]
    external_review = maturity["external_review"]
    authorizations = record["deployment_authorization"]

    if (
        self_validation["status"] == "passed"
        and self_validation["validated_commit"] != current_commit
    ):
        errors.append("passed self-validation must bind current_commit; use stale otherwise")
    if (
        external_review["status"] == "passed"
        and external_review["reviewed_commit"] != current_commit
    ):
        errors.append("passed external review must bind current_commit; use stale otherwise")

    for environment, authorization in authorizations.items():
        if (
            authorization["status"] == "allowed"
            and authorization["artifact_commit"] != current_commit
        ):
            errors.append(f"{environment} allowed authorization must bind current_commit")

    for environment in EXPERIMENTAL_AUTHORIZATIONS:
        if (
            authorizations[environment]["status"] == "allowed"
            and self_validation["status"] != "passed"
        ):
            errors.append(f"{environment} requires passed exact-version self-validation")

    for environment in HIGH_RISK_AUTHORIZATIONS:
        authorization = authorizations[environment]
        if authorization["status"] != "allowed":
            continue
        if external_review["status"] != "passed":
            errors.append(f"{environment} requires passed exact-version external review")
        required_constraints = {
            "cluster",
            "program_id",
            "idl_sha256",
            "mint",
            "upgrade_authority",
            "max_value_base_units",
        }
        missing = sorted(required_constraints - set(authorization["constraints"]))
        if missing:
            errors.append(f"{environment} missing constraints: {', '.join(missing)}")
    return errors


def validate_record(record: dict[str, Any]) -> list[str]:
    errors = schema_errors(record)
    if errors:
        return errors
    return semantic_errors(record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    arguments = parser.parse_args()
    record = json.loads(arguments.record.read_text(encoding="utf-8"))
    errors = validate_record(record)
    print(
        json.dumps(
            {
                "status": "failed" if errors else "passed",
                "record": arguments.record.as_posix(),
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
