# FC-PROTO-001 evidence

Initial implementation commit:
`9b8417dae614aba64e7f2b70ae6e69f643b2052b`

Accounting-review remediation commit:
`f76db337efc81614b103bbff9790ab49e0c5ca80`

Baseline:
`5573e73e2241a3ece86253aae6f1de6f60e95e48`

Scope:

- deterministic offline `Channel` v1 validation;
- deterministic offline `ChannelFunding` transition validation;
- accounting projection for `F = V + S + R` and
  `0 <= S <= A <= F - R`;
- lifecycle-specific accounting constraints for draft, funding, active,
  settling, closing, expired, and closed snapshots;
- full previous/after snapshot validation for funding and top-up, including
  immutable economic fields and permitted status transitions;
- canonical unsigned u64 amount bounds in both the schema and Python
  reference validator;
- schema lifecycle constraints for closing fields;
- no Cloud, wallet, signer, RPC, broadcast, or Solana program operation.

Verification:

| Command | Result |
|---|---|
| `python -m pytest` | 184 passed, 11 skipped |
| `python -m pytest tests/channels/test_channel.py tests/channels/test_foundation_contracts.py` | 79 passed |
| `python -m ruff check .` | passed |
| `python -m ruff format --check packages tests services scripts` | 41 files formatted |
| `npm ci && npm test` in the TypeScript protocol package | 8 passed; audit found 0 vulnerabilities |

Generated JUnit evidence is in `pytest-full.xml`.

Artifact hashes:

```text
SHA256(cumulative-channel-v1.json)
479145d2d8ba4a76d646e5b4e2991adfa57955c0d4cc5c1bd3f59b253adb6fce

SHA256(channel.schema.json)
5893b4606a809637185f89db358f325f98cf37e21469c2d5ad38ed0ffc222d82
```

Security statement:

- validation is fail-closed and rejects unknown object fields;
- unsigned decimal amounts reject floats, signs, and leading zeroes;
- lifecycle and accounting inconsistencies have stable error codes;
- successful validation proves only internal consistency of caller-provided
  data, not on-chain origin;
- the first independent accounting review requested lifecycle and transition
  changes; those changes are implemented in `f76db33...`;
- a second independent accounting review remains required before merge and
  before any money-moving work.

Governance note:

The canonical FC-PROTO-001 `allowed_paths` do not include `.agents/tasks/**` or
`docs/WORK_GRAPH.md`. Those files were intentionally not changed. The PR should
not be marked `done` until an independent reviewer approves the accounting
invariants and the coordinating work-graph owner records that decision.
