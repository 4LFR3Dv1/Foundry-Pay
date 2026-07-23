# FP-PROTO-002 cross-language evidence

Date: 2026-07-23

## Decision

Protocol v1 uses:

```json
{
  "amount_base_units": "1000000",
  "network": "solana:devnet",
  "capability": "solana.spl_transfer.v1",
  "expires_at": "2026-07-23T18:00:00Z"
}
```

Signed objects reject `null`, floats, NaN, Infinity, negative zero, and integers
outside JavaScript's safe range. Unicode is preserved exactly and is never
normalized silently. Arrays remain ordered; object property order is
immaterial.

## Shared conformance

Python and TypeScript consume:

- `conformance/vectors/protocol-v1.json`;
- `conformance/vectors/negative-v1.json`.

The positive vector contains expected canonical UTF-8 bytes encoded as hex and
the expected SHA-256 values. Both implementations assert the same artifacts.

## Verification

```text
python -m pytest tests/protocol
19 passed

npm test --prefix packages/external-execution-protocol/typescript
6 passed

python -m ruff check .
All checks passed!

python -m ruff format --check .
6 files left unchanged

python scripts/check_secrets.py
Secret guard passed (40 files scanned).
```

Acceptance:

- Python canonical bytes equal TypeScript canonical bytes: passed;
- Python SHA-256 equals TypeScript SHA-256: passed;
- positive vectors pass: passed;
- negative vectors fail: passed;
- single-field tampering changes hash: passed;
- array order remains material: passed;
- object property ordering is immaterial: passed;
- unsupported numeric values are rejected: passed.
