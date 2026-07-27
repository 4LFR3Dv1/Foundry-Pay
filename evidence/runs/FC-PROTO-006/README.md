# FC-PROTO-006 evidence

This evidence pack freezes the offline Foundry Channels v1 canonicalization,
domain registry, hash profiles, exact-byte vectors, negative rejections, and
legacy compatibility decision.

## Baseline

```text
execution baseline:
ac10151b74cdfb33638d3c28fb3607a134234057

required FC-PROTO-005 merge:
59f37870475df0f0ee9d7619be9d3eff7f5a16bd

required FC-CTRL-010 merge:
8117ef0c4237222edba93922307d8b652f82858d
```

## Reproduction

```text
python evidence/runs/FC-PROTO-006/generate_evidence.py
python -m pytest --junitxml evidence/runs/FC-PROTO-006/pytest-full.xml
python evidence/runs/FC-PROTO-006/generate_evidence.py
python -m ruff format --check .
python -m ruff check .
python scripts/check_secrets.py
```

The completed local run collected 461 tests: 450 passed and 11 environment
dependent chaos tests were skipped. The artifact manifest is generated from
file bytes and uses the evidence namespace; it is not an economic protocol
receipt.

## Compatibility

Reviewed Voucher and RecipientBinding hashes remain exact. Settlement, closure,
refund, recovery, and finalization economic preimages remain exact.

Voucher-ledger scope keys and settlement/refund journal chains receive an
explicit pre-runtime domain migration. Pre-FC-PROTO-006 local reference
databases must be rebuilt. No fallback is implemented.

## Non-claims

This evidence does not claim TypeScript or Rust conformance, ChannelVault,
on-chain verification, mainnet, production readiness, or economic completion.
