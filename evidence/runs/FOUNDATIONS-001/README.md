# FOUNDATIONS-001 evidence

This run records the architecture-foundation validation. It is not evidence of
a deployed ChannelVault or a live payment channel.

## Immutable inputs

- Foundry-Pay baseline:
  `a8631b081f40029c18b16098508c44540efbf77f`
- Solana-Agent baseline:
  `914eaf3c9b407f787c6f51d9886c6e86ae542335`

## Reproduce

```text
python scripts/check_channel_foundation.py
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
npm test --prefix packages/external-execution-protocol/typescript
git diff --check
```

## Artifacts

- `inventory.json`: machine-readable baseline and reuse disposition.
- `foundation-check.json`: schema, vector, accounting, document, and work-graph
  validation.

The tested implementation commit and artifact hashes are recorded below.

## Verified implementation

- implementation commit:
  `264a09fa1510aa707afff4a6b4c295cc72c15310`
- `foundation-check.json` SHA-256:
  `698a491190aa6756f6522d01872dd388432f4fe1f6a7b6b37fa149e3b3089c54`
- `inventory.json` SHA-256:
  `6edf62961fa160488de4a5c564492c521643417b5d047ead1011c8cb53845846`
- positive protocol vector SHA-256:
  `479145d2d8ba4a76d646e5b4e2991adfa57955c0d4cc5c1bd3f59b253adb6fce`

Validation result:

```text
foundation check: passed
schemas: 7 valid
positive vectors: 1 valid
negative mutations: 12/12 rejected as expected
accounting invariants: passed
work items: 38 complete contracts; exactly 5 ready
pytest: 106 passed, 11 skipped
ruff check/format: passed
secret guard: passed
TypeScript protocol tests: 8 passed
local Markdown links: passed
git diff --check: passed
```

## Limitations

- signatures in protocol vectors are shape fixtures and do not prove private
  key possession;
- identifiers are sanitized/synthetic devnet-shaped fixtures;
- no channel instruction was submitted to Solana;
- no Cloud, browser claim flow, signer, or ChannelVault was implemented;
- this run makes no production, mainnet, custody, audit, scale, or exactly-once
  claim.
