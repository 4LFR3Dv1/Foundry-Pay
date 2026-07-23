# FP-PROTO-007 obligation-bound commitment evidence

Date: 2026-07-23

Implementation commit:
`9b4f842ed4d69f8be424ddb2b0a0d18d65ebc97e`.

## Decision

The unreleased draft protocol remains version `1.0.0`.
`obligation_id` is now required in the normative `ExecutionCommitment`, uses
the canonical identifier grammar, and participates in RFC 8785
canonicalization and SHA-256.

The corrected normative vector produces:

```text
execution_commitment_hash =
sha256:3b9b4184175705cc125d979ae94ec3f05a541697c85245855ff5ab3b749a7a50
```

The live compatibility vector independently reproduces the Solana-Agent
SA-GW-002 commitment:

```text
execution_commitment_hash =
sha256:e5e6ec585f0e46a6a77a2c07c291d9bb1b0c02c9c375297abdf739b00421ee79
```

Source: `4LFR3Dv1/Solana-Agent` commit
`6bdecfbbcbc737ce8c5009cb9dd31e8b24fa64ec`.

## Verification

```text
python -m pytest tests/protocol
31 passed

npm test --prefix packages/external-execution-protocol/typescript
8 passed

python -m ruff check .
All checks passed!

python -m ruff format --check .
9 files already formatted

python scripts/check_secrets.py
Secret guard passed (47 files scanned).

python packages/external-execution-protocol/conformance/generate_vectors.py
SHA-256 before = SHA-256 after
```

## Acceptance

- Python and TypeScript canonical bytes and hashes agree: passed.
- Positive vector includes `obligation_id`: passed.
- Missing and invalid `obligation_id` are rejected: passed.
- Changing `obligation_id` changes the commitment hash: passed.
- Persisted obligation rebinding fails before any effect: passed.
- Fake executor constructs and reconstructs the corrected commitment: passed.
- Live Solana-Agent commitment is representable without compatibility logic:
  passed.
- Vector regeneration is deterministic: passed.
- Provenance is pinned in `provenance/REUSE_LEDGER.yaml`: passed.
