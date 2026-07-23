# FP-PROTO-003 fake executor evidence

Date: 2026-07-23

## Outcome

The fake external executor persists preparation, authorization consumption,
economic effect, status, and receipt in SQLite.

The injected `after_commit_before_response` failure occurs only after the
receipt and effect commit. A new executor process recovers the confirmed
receipt, refuses authorization replay, refuses a new request for the completed
obligation, and retains exactly one economic effect.

## Safety properties proved

- exact serialized message bytes are re-hashed during COMMIT;
- simulation attestation is re-hashed during COMMIT;
- execution commitment is reconstructed and re-hashed during COMMIT;
- authorization binds request, commitment, message hash, and signer;
- authorization must be authentic, active, short-lived, and single-use;
- authorization consumption is unique and recorded before effect insertion;
- `obligation_id` has a unique persisted effect;
- idempotency identifiers cannot be reused with different immutable inputs;
- receipt is durable before response;
- journal tampering is detected before effect.

## Focused verification

```text
python -m pytest tests/protocol/test_fake_executor.py
10 passed
```

Complete gate:

```text
python -m pytest
29 passed

npm test --prefix packages/external-execution-protocol/typescript
6 passed

python -m ruff check .
All checks passed!

python scripts/check_secrets.py
Secret guard passed (44 files scanned).
```

Covered scenarios:

- deterministic idempotent preparation;
- valid execution and receipt;
- expired authorization;
- non-single-use authorization;
- authorization outliving prepared execution;
- signature tampering;
- validly signed binding mismatch;
- idempotency conflict;
- persisted message tampering;
- persisted receipt tampering;
- response loss after commit;
- process recreation and recovery;
- authorization replay;
- second request for an executed obligation.

## Scope boundary

The HMAC authority is test-only. Production signing remains a separate
HSM/MPC/signer-boundary work item. The fake executor does not move funds or
connect to Solana.
