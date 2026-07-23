# FP-SIGN-001 exact-message signer evidence

Date: 2026-07-23

Implementation commit:
`31eb2f9cf28c23d332d9cfe1bd2370da141b984a`.

## Result

The signer boundary validates a short-lived, single-use
`ExecutionAuthorization`, verifies its Foundry authenticity, binds it to the
live SA-GW-002 request and commitment, recalculates SHA-256 over the exact
decoded message bytes, and delegates only those bytes to an injected signing
provider.

The accepted live bindings are:

```text
execution_commitment_hash =
sha256:e5e6ec585f0e46a6a77a2c07c291d9bb1b0c02c9c375297abdf739b00421ee79

prepared_message_hash =
sha256:85a6b98ca7c050ee9dcba7aa0750d876a8ef5fd084458e768200256a9950cba6
```

The production service accepts no raw asset signing material and has no RPC or
broadcast path. Authorization verification and asset signing are injected as
separate narrow interfaces suitable for an HSM, MPC, or remote signer.

## Verification

```text
python -m pytest
62 passed in 1.10s

python -m ruff check .
All checks passed!

python -m ruff format --check .
15 files already formatted

python scripts/check_secrets.py
Secret guard passed (61 files scanned).

git diff --check
passed
```

## Acceptance

- Valid live request, commitment, message hash, and authorization are accepted:
  passed.
- The provider receives exactly the authorized serialized message bytes:
  passed.
- Any changed message byte is rejected before provider invocation: passed.
- Invalid authorization authenticity is rejected before provider invocation:
  passed.
- Request, commitment, message hash, and signer rebinding are rejected: passed.
- Future, expired, or non-single-use authorization is rejected: passed.
- Durable claim occurs before the external signing call: passed.
- Concurrent use invokes the signing provider exactly once: passed.
- Completed authorization remains consumed across restart: passed.
- Unknown provider outcome becomes `needs_recovery` and is not retried: passed.
- No raw asset key, Solana RPC, or broadcast capability is exposed: passed.
