# FP-AUTH-001 exact-message authorization evidence

Date: 2026-07-23

Implementation commit:
`69604b125bbc8c1f15a3bf8c9041729305cb1330`.

## Result

Foundry independently verifies an authoritative `EconomicPlan` and a closed
`PreparedExecution`, reconstructs all material hashes including the
obligation-bound commitment, and emits a short-lived, single-use
`ExecutionAuthorization`.

The live SA-GW-002 fixture is accepted with:

```text
execution_commitment_hash =
sha256:e5e6ec585f0e46a6a77a2c07c291d9bb1b0c02c9c375297abdf739b00421ee79
```

The implementation provides only an injected authorization-signature
interface. It contains no Solana asset key, transaction-signing, RPC, or
broadcast capability.

## Verification

```text
python -m pytest
48 passed in 0.91s

python -m ruff check .
All checks passed!

python -m ruff format --check .
12 files already formatted

python scripts/check_secrets.py
Secret guard passed (55 files scanned).

git diff --check
passed
```

## Acceptance

- Live commitment `e5e6...` is accepted: passed.
- Economic plan hash is recalculated from the authoritative plan: passed.
- Prepared message hash is recalculated from exact decoded bytes: passed.
- Simulation attestation and execution commitment hashes are recalculated:
  passed.
- `obligation_id`, request, executor, signer, fee, and program constraints are
  bound to Foundry authority: passed.
- Message, simulation, commitment, identity, and constraint tampering fail:
  passed.
- Authorization cannot outlive the plan, simulation, or prepared execution:
  passed.
- Concurrent issuance creates exactly one active authorization: passed.
- Issuance and consumption survive process restart: passed.
- Consumption is single-use and replay fails: passed.
- No Solana signing material or broadcast path is accessible: passed.
