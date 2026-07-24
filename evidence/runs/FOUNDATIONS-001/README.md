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
- reviewed head before final findings:
  `b64b1e5beaef0df565e9f4d72e769cc806444d5f`
- final adjustments commit:
  `380b3eb9636a3c0e5f3dcdfec5a59a0fb1309e97`
- reason for additional commits: sanitize a public fixture after a false-positive
  secret detection, then close the issued-voucher/close race and persist
  sanitized critical security gates.
- `foundation-check.json` SHA-256:
  `d755a0369aaa6e4153a061ab4500a4ff682ec5bc3f9a114dc54babf619cc3bc3`
- `inventory.json` SHA-256:
  `b43c4911b32721a88a521e7e899d6a552750d5a460c6b1933c1a4b4007e0fc67`
- positive protocol vector SHA-256:
  `479145d2d8ba4a76d646e5b4e2991adfa57955c0d4cc5c1bd3f59b253adb6fce`
- close-race vector SHA-256:
  `32bd39287f70fbf9b89e59ff6ea9e77df231f9736a12e8358065e06ee135fb29`
- closure schema SHA-256:
  `9349e661c11ae8afd36b52bcae1a096a75482c81ad70efa224f5bb7a1676038d`
- sanitized security-gates SHA-256:
  `e9b7d75bc58f4081e7c6f6ddee962bb8372f2adf3edfce5988827f44a10819a5`

Validation result:

```text
foundation check: passed
schemas: 7 valid
positive vectors: 2 valid, including issued-voucher close race
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
- independent external security review was not performed;
- this run makes no production, mainnet, custody, audit, scale, or exactly-once
  claim.
