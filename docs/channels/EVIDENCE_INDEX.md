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
| every required work item has a complete contract and every `ready` item has completed dependencies | [work items](work-items.yaml) | same command |
| authority, state, link, recovery, and repository boundaries are accepted decisions | [decision register](DECISIONS.md) and five ADRs | document review |
| required threats have preventive, detective, recovery, evidence, and residual-risk treatment | [threat model](THREAT_MODEL.md) | security design review |
| three critical design risks are versioned as public release gates without exploit detail | [security gates](SECURITY_GATES.md) | register review |

Generated run artifacts live in
`evidence/runs/FOUNDATIONS-001/`. Their hashes are recorded in that directory's
README after the validation run.

## Integrated offline gates

| Work item | Merge commit | Evidence |
|---|---|---|
| FC-PROTO-001 | `0911bb9d5128c4dc9dccf82437a0dce0c0b53896` | `evidence/runs/FC-PROTO-001/` |
| FC-PROTO-002 | `a27a0e3daf0ecf2d0f11471d3055283cf6859db7` | `evidence/runs/FC-PROTO-002/` |
| FC-PROTO-003 | `2a5a7f8392c5af96e59d19585a83578761c2606b` | `evidence/runs/FC-PROTO-003/` |
| FC-SEC-003 | `ec8db6ba213d40718b3d9e5593826021d36e0e77` | `evidence/runs/FC-SEC-003/` |
| FC-GOV-001 | `6207df8d4291f8e832fe3758a39ffd267524b447` | `evidence/runs/FC-GOV-001/` |
| FC-PROTO-007 | `63da85549bcd247a0510e8af18cddc30d8c53bb2` | `evidence/runs/FC-PROTO-007/` |

These merges authorize the next offline protocol work only. They do not prove
ChannelVault, Solana execution, a deployed consumer frontend, or product demand.

## Next security gate

The frozen [FC-SEC-002 contract](security/FC-SEC-002-CONTRACT.md) separates:

```text
v1 replay resistance
cross-type and cross-profile collision resistance
version downgrade, rotation, revocation, and migration policy
```

FC-SEC-002 may be integrated as self-validated evidence, but that state permits
only offline and local-validator experimentation. Devnet, mainnet, real-value
use, and claims of independent external review remain blocked.

The gate distinguishes forbidden economic or authority effects from permitted
audit effects. A rejected attempt may produce a durable `rejected` journal
event, but it cannot advance verification, activation, authorization,
completion, or any economic total.

## Evidence maturity and authorization

Evidence maturity and operational authorization are independent records under
[FC-ADR-009](ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md)
and the executable
[component maturity schema](../../contracts/governance/component-maturity.schema.json).

The model distinguishes:

```text
work item delivered
self-validation passed
external review passed for an exact commit
deployment authorized for an exact artifact and environment
```

FC-GOV-001 does not assert an external review of FC-PROTO-007 and does not
authorize ChannelVault, devnet, mainnet, or real-value execution. After this
policy is integrated, PR #34 must incorporate the governance baseline and
regenerate its own exact-head evidence before it can be merged as
self-validated.

## Explicitly unproven

- a deployed ChannelVault program;
- real channel funding, activation, claim, settlement, close, or refund;
- safe production custody or hosted operations;
- mainnet readiness, external audit, or proven scale;
- exactly-once blockchain execution;
- external user comprehension or adoption;
- independent external security review.

These require later work items and cannot be inferred from this foundation.
