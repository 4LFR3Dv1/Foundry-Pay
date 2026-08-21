# Foundry Channels program

- Program: Foundry Channels
- Foundation work item: `FOUNDATIONS-001`
- Status: foundation integrated; protocol/model baseline self-validated; operational execution not authorized
- Scope: public protocol, executor-preparation contracts, product validation, and a gated future devnet vertical slice
- Program opened: 2026-07-24

## Executive summary

Foundry Channels turns a link from a one-time payment pointer into a persistent
relationship for transferring value. The first primitive is a unidirectional,
funded, cumulative channel that one sender can update and one recipient can
settle on demand.

The architecture has six strict authorities:

1. the sender creates economic intent and signs cumulative vouchers;
2. the public Foundry Channels protocol defines objects, hashes, invariants, and
   verification;
3. a future operational ChannelVault would enforce funding, monotonic
   activation, recipient binding, settlement, close, and refund on Solana;
4. a private Foundry Pay Cloud may resolve links, relay signed objects, notify,
   index, and orchestrate, but cannot manufacture rights;
5. Solana-Agent prepares, simulates, executes, confirms, recovers, and produces
   technical evidence only under the capability and authorization boundaries
   that have actually been implemented and released;
6. a signer signs only the exact Solana message covered by a valid execution
   commitment and applicable authorization.

An off-chain signed voucher is `issued`; only a sequence accepted by an
operational ChannelVault could become `activated` and economically settleable in
v1. The existing offline ledger/model cannot create that on-chain authority.

## Authority surfaces

This program keeps direction, execution, and proof separate:

- [`../../ROADMAP.md`](../../ROADMAP.md) — strategic direction;
- [`WORK_GRAPH.md`](WORK_GRAPH.md) — human-readable execution authority;
- [`work-items.yaml`](work-items.yaml) — executable work-item registry and path contracts;
- [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) — demonstrated results and limitations;
- [`ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md`](ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md) — maturity and deployment-authorization policy.

`done` means delivered/integrated. It does not mean externally reviewed or
authorized for deployment/value.

## Immutable origin baselines

The original foundation pinned these evidence inputs:

| Repository | Commit | Role |
|---|---|---|
| `4LFR3Dv1/Solana-Agent` | `914eaf3c9b407f787c6f51d9886c6e86ae542335` | external Solana execution, recovery, and technical evidence baseline |
| `4LFR3Dv1/Foundry-Pay` | `a8631b081f40029c18b16098508c44540efbf77f` | protocol, authorization, reconciliation, conformance, and failure-tooling baseline |

These SHAs remain historical origin baselines, not claims that the program has
stopped at those commits. Current evidence is indexed separately.

## Product thesis

> Open a channel. Share a link. Send as often as you want.

The link is a discovery/delivery surface, not economic authority. The right is
represented by the signed, versioned protocol and—when operational execution is
later authorized—funded on-chain state.

See [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md) for the complete user model.

## Current integrated baseline

The program has moved well beyond the initial architecture foundation.
Demonstrated offline/model/integration work includes:

- `FC-PROTO-001` through `FC-PROTO-007`: channel/funding validation, cumulative
  voucher semantics, recipient binding, settlement/reconciliation, close/refund,
  canonicalization, and Python/TypeScript/Rust self-conformance;
- `FC-SEC-001` through `FC-SEC-004`: threat modeling, adversarial/replay and
  lifecycle properties, claim-link handling, and offline concurrency/
  linearizability evidence;
- `FC-SOL-001` through `FC-SOL-005`: ChannelVault design, account and instruction
  contracts, transition invariants, concurrency-related model work, and
  upgrade/migration/governance policy;
- `SA-CHAN-000` through `SA-CHAN-001B`: fail-closed adapter contracts,
  descriptive discovery, durable operation commitments, funding identity, and a
  fixture-only common preparation boundary across the independent Solana-Agent
  repository.

These are protocol/model/integration results. They do **not** establish a
deployed ChannelVault, transaction handlers, signer access, RPC execution, live
channel funding, or deployment authorization.

## Current execution frontier

The delegated work graph currently exposes three technical items as ready:

- `SA-CHAN-002` — initialize/funding/activation fixture preparation;
- `SA-CHAN-003` — settlement fixture preparation;
- `FC-FAIL-003` — offline settlement/lifecycle failure lab.

After `SA-CHAN-002` and `SA-CHAN-003`, the graph can release the bounded
successors for binding/lifecycle preparation, status/recovery, and channel
evidence/conformance if their dependencies and contracts are satisfied.

No operational ChannelVault implementation is authorized by this frontier.

## Human validation frontier

The public `FC-VAL-003` kit defines the 30-second proposition-comprehension
protocol. The Roadmap correctly treats human comprehension as a current
strategic priority, but the protocol itself records an unresolved authority
gate:

- raw research belongs outside this public repository;
- no authorized private research-storage/consent system has yet been
  established by the public work item;
- recruitment therefore remains prohibited until the private checklist,
  privacy review, immutable run manifest, and consent/storage boundaries are
  actually approved.

See [`validation/FC-VAL-003/README.md`](validation/FC-VAL-003/README.md).

A `ready` work-item label must not be interpreted as permission to collect human
data contrary to those stop conditions.

## First end-to-end product proof target

The original target remains useful and is still **not completed**:

```text
Alice funds 100 fixture units on devnet
→ issues and activates cumulative totals 10, 25, then 40
→ Bob opens a protected claim link
→ Bob binds an existing wallet
→ Bob requests settlement of 40
→ Foundry authorizes exact prepared bytes
→ Solana-Agent submits once
→ RPC response is lost
→ recovery finds the persisted signature
→ independent reconciliation observes 40 settled
→ channel remains active with 60 unallocated units
```

Reaching this proof requires a later explicit authorization step from the
current model/fixture boundary into operational ChannelVault implementation and
then an environment-specific local-validator/devnet gate.

## MVP target

If and when the operational vertical slice is authorized, the bounded MVP target
remains:

- Solana devnet;
- one explicitly identified SPL fixture;
- one sender and one recipient;
- one-way funded channel;
- cumulative activated vouchers;
- partial or total settlement;
- top-up, close grace period, and refund according to the accepted protocol;
- protected claim link and an existing recipient wallet;
- non-authoritative hosted relay where separately authorized;
- recovery by persisted signature;
- reproducible evidence.

Excluded from that MVP target:

- mainnet or real-value operation;
- custody, fiat, card, swaps, bridges, DEX, or token issuance;
- bidirectional, multi-hop, cross-chain, or per-second streaming channels;
- a complete wallet or native mobile application;
- production multi-tenancy, billing, automated compliance, or SLAs.

## Product and security principles

- External-first: network execution remains outside Foundry Pay.
- Protocol-first: signed rights use closed, versioned, canonical objects.
- Hosted convenience, cryptographic right: a server may help find and deliver a
  right but may not create it.
- Monotonic cumulative state: authorized totals increase inside an epoch.
- Fail closed: uncertainty becomes `needs_recovery` or `needs_review`.
- Consumer-simple: protocol complexity must not leak into the primary user
  proposition.
- Evidence-bounded: every claim names what was actually observed and what
  remains unproven.

## Remaining capability gaps

The material gaps are no longer the original protocol foundation. They are:

- complete the remaining Solana-Agent fixture-preparation/status/recovery/
  evidence boundaries;
- establish authorized private research infrastructure and perform human
  comprehension validation;
- make a new explicit governance decision before implementing operational
  ChannelVault handlers;
- if authorized, prove the bounded local-validator/devnet vertical slice;
- validate product usability and repeated-use intent only after prerequisite
  comprehension/product gates are satisfied;
- obtain independent external review where required before real-value or
  mainnet authorization.

The detailed dependency truth lives in [`WORK_GRAPH.md`](WORK_GRAPH.md), not in
this prose summary.

## Explicit non-claims

This program does not currently establish:

- a deployed or operational ChannelVault;
- real channel funding, activation, claim, settlement, close, or refund;
- safe production custody or hosted operations;
- mainnet readiness or real-value authorization;
- externally audited security where no exact-version review is recorded;
- exactly-once blockchain execution;
- proven user comprehension, product demand, or independent adoption;
- production scale.
