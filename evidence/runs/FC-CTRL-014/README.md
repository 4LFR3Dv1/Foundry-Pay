# FC-CTRL-014 evidence

This coordination item freezes the FC-PROTO-007 execution boundary without
implementing a runner, comparator, dependency, or CI job.

## Baseline

```text
Foundry-Pay main:
17b656cbdd6ae53cece9cebb9123058c03e67b82

FC-PROTO-006 merge:
959cd8db597510a5fc58ee6acd421a1ae6bacb42
```

## Frozen inventory

```text
positive vectors: 8
negative vectors: 20
rejection stages: 6
stable rejection codes: 18
implementations: Python, TypeScript, Rust
runner output: closed UTF-8 JSONL
```

## Decisions

- Positive agreement requires the same bytes, byte length, and SHA-256.
- Negative agreement requires the same rejection stage and code.
- Runners compute from `source_json` or `source_bytes_hex`.
- Expected output fields are never computation inputs.
- An expected-output poisoning test is mandatory.
- Implementations cannot import, invoke, generate, or read each other.
- The comparator validates and compares only; it performs no protocol logic.
- Frozen FC-PROTO-006 inputs remain unchanged.

## Residual gate

FC-PROTO-007 remains blocked until this coordination PR is reviewed and
integrated. The functional PR must add exact lockfiles, record dependency
provenance, run all three implementations, and publish independently reviewed
evidence.

## Validation

```text
foundation checker: passed
coordination JSON/YAML/schema validation: passed
focused canonicalization/foundation tests: 83 passed
full regression: 461 passed, 11 skipped
ruff check --no-cache: passed
ruff format --no-cache --check: 56 files already formatted
secret scan: 350 files scanned, passed
frozen FC-PROTO-006 artifact diff: empty
git diff --check: passed
```

The skipped tests require the pinned external Solana-Agent chaos checkout that
CI installs. No skip is part of the new coordination contract.
