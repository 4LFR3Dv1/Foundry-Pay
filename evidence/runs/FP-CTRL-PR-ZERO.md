# FP-CTRL PR zero evidence

Date: 2026-07-23
Scope: control baseline, external-first ADR, protocol draft, canonicalization
reference, conformance vector, and Solana-Agent baseline.

## Foundry Pay verification

```text
python -m ruff format --check .
6 files already formatted

python -m ruff check .
All checks passed!

python scripts/check_secrets.py
Secret guard passed (31 files scanned).

python -m pytest
13 passed
```

## Solana-Agent characterization

Repository: `4LFR3Dv1/Solana-Agent`
Commit: `6023d78b10b31b47a1beeecd438d67afbc722bd4`

```text
python -m pytest -q
115 passed, 2 skipped
```

Skipped tests require the pinned Solana/Anchor integration toolchain. No
Solana-Agent source file was modified.

## Provenance

No external source code was copied. Candidate repositories without resolved
licenses remain reference-only.
