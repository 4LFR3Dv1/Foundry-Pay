# FC-PROTO-001 evidence

Implementation commit:
`9b8417dae614aba64e7f2b70ae6e69f643b2052b`

Baseline:
`5573e73e2241a3ece86253aae6f1de6f60e95e48`

Scope:

- deterministic offline `Channel` v1 validation;
- deterministic offline `ChannelFunding` transition validation;
- accounting projection for `F = V + S + R` and
  `0 <= S <= A <= F - R`;
- schema lifecycle constraints for closing fields;
- no Cloud, wallet, signer, RPC, broadcast, or Solana program operation.

Verification:

| Command | Result |
|---|---|
| `python -m pytest` | 140 passed, 11 skipped |
| `python -m pytest tests/channels/test_channel.py tests/channels/test_foundation_contracts.py` | 35 passed |
| `python -m ruff check .` | passed |
| `python -m ruff format --check packages tests services scripts` | 41 files formatted |
| `npm ci && npm test` in the TypeScript protocol package | 8 passed; audit found 0 vulnerabilities |

Generated JUnit evidence is in `pytest-full.xml`.

Artifact hashes:

```text
SHA256(cumulative-channel-v1.json)
479145d2d8ba4a76d646e5b4e2991adfa57955c0d4cc5c1bd3f59b253adb6fce

SHA256(channel.schema.json)
f95bca86af8bbc174d74ce6db8fbd00153f972f3c77428d6f38e721d79ad3b69
```

Security statement:

- validation is fail-closed and rejects unknown object fields;
- unsigned decimal amounts reject floats, signs, and leading zeroes;
- lifecycle and accounting inconsistencies have stable error codes;
- successful validation proves only internal consistency of caller-provided
  data, not on-chain origin;
- independent accounting review remains required before money-moving work.

Governance note:

The canonical FC-PROTO-001 `allowed_paths` do not include `.agents/tasks/**` or
`docs/WORK_GRAPH.md`. Those files were intentionally not changed. The PR should
not be marked `done` until an independent reviewer approves the accounting
invariants and the coordinating work-graph owner records that decision.
