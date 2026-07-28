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
| FC-SEC-002 | `0d203389052a78d6cdec5b565ca28e605dad13fb` | `evidence/runs/FC-SEC-002/` |
| FC-SOL-002 | `818f565977766fbc3ddd05f24ad002ea04eb816e` | `evidence/runs/FC-SOL-002/` |
| SA-CHAN-000 | `49c62b6cfab0344a870bb285512df1d494eb6f03` | `evidence/runs/SA-CHAN-000/` |
| FC-SOL-003 | `192bd40245244cfd540c67f880104259b5190379` | `evidence/runs/FC-SOL-003/` |
| FC-SOL-003A | `aaffd54d0712dc7b0add981d06923dab00e4aba1` | `evidence/runs/FC-SOL-003A/` |
| FC-SOL-004 | `3f1740e70abb9ee67f7b83130fa5aef2a76befb8` | `evidence/runs/FC-SOL-004/` |
| FC-SEC-004 | `fbc5c43613d8c5535674eb398ad34387ce745854` | `evidence/runs/FC-SEC-004/` |
| FC-SOL-005 | `102c9dfec61131ad1b6682ecc4c9fe70d7ff57f1` | `evidence/runs/FC-SOL-005/` |
| SA-CHAN-001 | `0804965a25c8e5e52fc836b96f71929ac17c9198` | `Solana-Agent/evidence/runs/SA-CHAN-001/` |

These merges authorize the next offline protocol work only. They do not prove
ChannelVault, Solana execution, a deployed consumer frontend, or product demand.

PR #44 integrated the local-validator-only account model with functional head
`d6933604...`, evidence head `d84cea1f...`, merge `818f5659...`, and green main
CI run `30362592323`. PR #45 integrated the offline fake adapter with functional
head `7513587c...`, evidence head `c918ce1d...`, merge `49c62b6c...`, and green
main CI run `30364372600`. Both remain self-validated with external review
`not_performed`; devnet, mainnet, real assets, and production-security claims
remain blocked.

PR #48 integrated the experimental ChannelVault instruction contract with
functional head `2b6b5e4c...`, evidence head `097a03c9...`, merge
`192bd402...`, and green main CI run `30371165634`. It freezes serialization,
account metas, exact Ed25519 layouts, lifecycle projections, events, errors,
and deterministic negative fixtures. It does not implement an entrypoint,
economic handler, CPI, token transfer, deployment, or consumer integration.
External Solana instruction and Ed25519 review remains `not_performed`.

PR #55 integrated the pure ChannelVault transition model with functional head
`da8baf5f...`, evidence head `0efc701d...`, merge `3f1740e7...`, and green
main CI run `30379326962`. Its 1,536 generated property cases and bounded
exploration of 703 states and 4,732 transitions found zero invariant
violations within the published model and bounds. It is not formal
verification, a Solana runtime program, local-validator execution, deployment,
or external review.

PR #58 integrated the offline concurrent transition harness with functional
head `24588859...`, evidence head `9fd8f17e...`, merge `fbc5c436...`, and
green main CI run `30390747057`. Its 14 bounded schedules all have explicit
serial witnesses, and 512 property cases found no violation within the
published versioned-snapshot model and bounds. It does not prove Solana
runtime account locking, CPI rollback, validator scheduling, formal
verification, or external review. No handler or deployment gate was released.

PR #61 integrated the offline upgrade-governance model with functional head
`8664401b...`, evidence head `3e913c17...`, merge `102c9dfe...`, and green
main CI run `30394123710`. It validates threshold/timelock boundaries,
compatible versus isolated semantic changes, exit-preserving pause policy, and
active-right migration preservation. It does not test the Solana loader,
ProgramData, a real multisig/timelock, deployed-build reproduction, or any
deployment environment.

Solana-Agent PR #14 integrated descriptive ChannelVault discovery with
functional head `3d8b71a7...`, evidence head `1a588b6a...`, merge
`0804965a...`, and green main CI run `30403768939`. It pins Foundry-Pay commit
`7c718c42...` plus raw hashes `08a7d25c...` (490-byte account layout),
`ba09713e...` (instruction registry), and `4a5a7fc5...` (signed-message
registry). It reports preparation, execution, status, recovery, and deployment
support as false. No Program ID, network, genesis, handler, transaction,
local-validator run, or external review is inferred.

## Integrated security gate

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

PR #40 was integrated with functional head `e785dedd...`, evidence head
`dc0ff464...`, merge `0d203389...`, and green main CI run `30310413080`.
External review remains `not_performed`. The integration releases only
`FC-SOL-002` account-layout work and the transport-independent `SA-CHAN-000`
fake adapter. Later ChannelVault instructions, on-chain invariant gates,
failure-lab work, devnet, mainnet, and real-value use remain blocked.

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
