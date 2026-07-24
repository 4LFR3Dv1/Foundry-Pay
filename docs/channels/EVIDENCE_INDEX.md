# Foundry Channels evidence index

This index separates demonstrated repository facts from proposed Channels
behavior. The ChannelVault program and hosted product do not exist in this
foundation and are not presented as evidence.

## Immutable baselines

| Claim | Evidence | Commit |
|---|---|---|
| Solana-Agent provides governed external execution, durable journaling, status/recovery, and technical evidence | [inventory](INVENTORY.md), upstream source and tests identified there | `914eaf3c9b407f787c6f51d9886c6e86ae542335` |
| Foundry-Pay provides exact authorization, signer isolation, reference reconciliation, fake execution, failure tooling, and evidence | [inventory](INVENTORY.md), local source and tests identified there | `a8631b081f40029c18b16098508c44540efbf77f` |
| no Solana-Agent kernel was copied for this foundation | [reuse ledger](../../provenance/REUSE_LEDGER.yaml) and branch diff | both commits above |

## Foundation evidence

| Claim | Evidence | Reproduction |
|---|---|---|
| seven Draft 2020-12 schemas are structurally valid | `contracts/channel/*.schema.json` and `foundation-check.json` | `python scripts/check_channel_foundation.py` |
| cumulative vouchers hash deterministically and form an activation chain | [positive vector](../../contracts/channel/test-vectors/positive/cumulative-channel-v1.json) | same command |
| required replay, monotonicity, funding, binding, expiry, and settlement mutations reject | [negative vectors](../../contracts/channel/test-vectors/negative/) | same command |
| accounting satisfies `F = V + S + R` and `0 <= S <= A <= F - R` | positive vector and `foundation-check.json` | same command |
| exactly five first work items are ready and all required items have complete contracts | [work items](work-items.yaml) | same command |
| authority, state, link, recovery, and repository boundaries are accepted decisions | [decision register](DECISIONS.md) and five ADRs | document review |
| required threats have preventive, detective, recovery, evidence, and residual-risk treatment | [threat model](THREAT_MODEL.md) | security design review |

Generated run artifacts live in
`evidence/runs/FOUNDATIONS-001/`. Their hashes are recorded in that directory's
README after the validation run.

## Explicitly unproven

- a deployed ChannelVault program;
- real channel funding, activation, claim, settlement, close, or refund;
- safe production custody or hosted operations;
- mainnet readiness, external audit, or proven scale;
- exactly-once blockchain execution;
- external user comprehension or adoption.

These require later work items and cannot be inferred from this foundation.
