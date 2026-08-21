# Foundry Channels work graph

This file is the human-readable execution-authority surface for Foundry
Channels. The machine-oriented work-item registry is
[`work-items.yaml`](work-items.yaml).

Status values are `blocked`, `ready`, `active`, `review`, and `done`.

Status semantics:

- `blocked`: a dependency, authority gate, or stop condition prevents the work;
- `ready`: dependencies permit bounded work under its task contract, but no path
  is owned until the item is activated;
- `active`: the work item owns its allowed paths and is being executed;
- `review`: implementation/evidence is awaiting its required integration gate;
- `done`: delivered and integrated; this does not imply external review or
  deployment authorization.

`FOUNDATIONS-001` is integrated. Its completion established the architecture
foundation but did **not** authorize an operational ChannelVault, a deployment
environment, mainnet, or real-value use.

The maturity/deployment rule is governed by
[`ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md`](ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md):

```text
work item delivered
!= self-validation passed
!= external review passed
!= deployment authorized
```

Evidence and historical integration records live in
[`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md). Strategic priority lives in the
repository [`ROADMAP.md`](../../ROADMAP.md). Neither surface releases work by
itself.

## Current frontier

The current executable technical frontier is intentionally narrow:

| Work item | Status | Capability |
|---|---|---|
| SA-CHAN-002 | ready | initialize/funding/activation fixture preparation |
| SA-CHAN-003 | ready | settlement fixture preparation |
| FC-FAIL-003 | ready | offline settlement/lifecycle failure lab |

When `SA-CHAN-002` and `SA-CHAN-003` are integrated, their exact successors may
become eligible according to the graph below. No handler, signer access, RPC
execution, local-validator execution, or deployment environment is released by
these `ready` states.

Human validation is a separate authority boundary. `FC-VAL-003` has a public
protocol kit and remains `ready` at the work-item level for bounded
protocol/privacy preparation, but **human recruitment is currently prohibited**.
The private research-storage, consent, privacy-review, and immutable-run-manifest
gates in
[`validation/FC-VAL-003/README.md`](validation/FC-VAL-003/README.md) must be
satisfied before participant work begins. `ready` does not override that stop
condition.

## Epic A — Control and decision

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-CTRL-001 | done | FOUNDATIONS-001 | program, thesis, scope, and non-goals |
| FC-CTRL-002 | done | FC-CTRL-001 | authority, state machines, and work graph |
| FC-CTRL-003 | done | FC-CTRL-001 | immutable origin baselines |
| FC-CTRL-004 | done | FC-CTRL-003 | reuse ledger and gap matrix |
| FC-CTRL-005 | done | FC-CTRL-001 | public/private and repository boundary |
| FC-CTRL-006 | done | FC-PROTO-001, FC-PROTO-002, FC-PROTO-003, FC-SEC-003 | reconcile initial integrated protocol gates |
| FC-CTRL-007 | done | FC-PROTO-004 | reconcile settlement integration |
| FC-CTRL-008 | done | FC-CTRL-007 | authorize close-race vector migration |
| FC-CTRL-009 | done | FC-CTRL-008 | authorize close-race checker migration |
| FC-CTRL-010 | done | FC-PROTO-005 | reconcile close/refund integration |
| FC-CTRL-011 | done | FC-CTRL-010 | authorize FC-PROTO-006 normative paths |
| FC-CTRL-012 | done | FC-CTRL-011 | authorize canonicalization package marker |
| FC-CTRL-013 | done | FC-PROTO-006 | reconcile canonicalization integration |
| FC-CTRL-014 | done | FC-CTRL-013 | freeze cross-language conformance contract |
| FC-GOV-001 | done | FC-CTRL-014 | separate delivery, review, maturity, and deployment authorization |
| FC-CTRL-015 | done | FC-PROTO-007, FC-GOV-001 | reconcile governed conformance integration |
| FC-CTRL-016 | done | FC-CTRL-015, FC-GOV-001 | freeze FC-SEC-002 contract |
| FC-CTRL-017 | done | FC-CTRL-016 | classify forbidden vs permitted rejection effects |
| FC-CTRL-018 | done | FC-CTRL-017 | align FC-SEC-002 dependencies |
| FC-CTRL-019 | done | FC-SEC-002 | reconcile security integration |
| FC-CTRL-020 | done | FC-CTRL-019, FC-SEC-002 | freeze fixed-width account model contract |
| FC-CTRL-021 | done | FC-CTRL-019, SA-CHAN-000 | freeze authority-free fake-adapter contract |
| FC-CTRL-022 | done | FC-SOL-002, SA-CHAN-000 | reconcile account model and fake adapter |
| FC-CTRL-023 | done | FC-CTRL-022, FC-SOL-002, FC-SEC-002 | freeze instruction-contract boundary |
| FC-CTRL-024 | done | FC-SOL-003 | reconcile instruction-contract integration |
| FC-CTRL-025 | done | FC-CTRL-024, FC-SOL-003 | freeze ABI implementability corrections |
| FC-CTRL-026 | done | FC-SOL-003A | reconcile operability correction |
| FC-CTRL-027 | done | FC-CTRL-026, FC-SOL-003A | freeze transition-model semantics |
| FC-CTRL-028 | done | FC-CTRL-027, FC-SOL-003A | make historical manifest verification commit-aware |
| FC-CTRL-029 | done | FC-SOL-004 | reconcile transition-model integration |
| FC-CTRL-030 | done | FC-CTRL-029, FC-SOL-004 | freeze concurrency/linearization contract |
| FC-CTRL-031 | done | FC-SEC-004 | reconcile concurrency integration |
| FC-CTRL-032 | done | FC-SEC-004, FC-SOL-003A | freeze governance/migration preconditions |
| FC-CTRL-033 | done | FC-SOL-005 | reconcile governance integration without deployment authority |
| FC-CTRL-034 | done | SA-CHAN-001 | reconcile descriptive discovery |
| FC-CTRL-035 | done | SA-CHAN-001A | reconcile operation-commitment integration |
| FC-CTRL-036 | done | FC-CTRL-035, SA-CHAN-001A | freeze funding identity and fixture-only preparation profile |
| FC-CTRL-037 | done | SA-CHAN-001B | reconcile common fixture-preparation boundary |

## Epic B — Channel protocol

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-PROTO-001 | done | FOUNDATIONS-001 | executable `Channel` and `ChannelFunding` validation |
| FC-PROTO-002 | done | FOUNDATIONS-001 | cumulative voucher verifier and monotonic reference ledger |
| FC-PROTO-003 | done | FOUNDATIONS-001 | claim and dual-signature recipient binding verifier |
| FC-PROTO-004 | done | FC-PROTO-001, FC-PROTO-002, FC-PROTO-003 | settlement and reconciled receipt reference runtime |
| FC-PROTO-005 | done | FC-PROTO-001, FC-PROTO-002 | close, expiry, epoch, and refund semantics |
| FC-PROTO-006 | done | FC-PROTO-001, FC-PROTO-002, FC-PROTO-003 | normative canonicalization and hashes |
| FC-PROTO-007 | done | FC-PROTO-006, FC-CTRL-014, FC-GOV-001 | self-validated Python/TypeScript/Rust conformance |

## Epic C — Security

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-SEC-001 | done | FOUNDATIONS-001 | comprehensive design threat model |
| FC-SEC-002 | done | FC-PROTO-002, FC-PROTO-006, FC-PROTO-007, FC-CTRL-017 | replay, semantic-collision, downgrade, and lifecycle property suite |
| FC-SEC-003 | done | FOUNDATIONS-001 | claim-link handling and secret non-disclosure kit |
| FC-SEC-004 | done | FC-PROTO-004, FC-SOL-004, FC-CTRL-030 | offline concurrency and linearizability evidence |
| FC-SEC-005 | blocked | FC-PROTO-004, SA-CHAN-004 | Cloud outage and self-recovery proof |

## Epic D — ChannelVault model

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-SOL-001 | done | FOUNDATIONS-001 | ChannelVault design specification |
| FC-SOL-002 | done | FC-PROTO-001, FC-SEC-002 | fixed-width ChannelState PDA and classic SPL Token vault layout model |
| FC-SOL-003 | done | FC-PROTO-002, FC-PROTO-003, FC-PROTO-004, FC-PROTO-005, FC-SOL-002, FC-SEC-002 | instruction/account-meta/Ed25519/lifecycle/event/error contracts; fixture model only |
| FC-SOL-003A | done | FC-SOL-003, FC-CTRL-025 | initialization-meta correction, permissionless settlement, bounded claim window |
| FC-SOL-004 | done | FC-SOL-003A, FC-SEC-002, FC-CTRL-027 | pure transition invariants and bounded/property exploration |
| FC-SOL-005 | done | FC-SOL-003A, FC-SEC-004, FC-CTRL-032 | upgrade, migration, rights-preservation, and governance policy |

**No operational ChannelVault program implementation is authorized by these
items.** A later governance decision must explicitly release implementation and
then environment-specific execution.

## Epic E — Solana-Agent integration

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| SA-CHAN-000 | done | FC-PROTO-007, FC-SEC-002, FC-CTRL-021 | draft capability contracts and adversarial fake adapter; offline only |
| SA-CHAN-001 | done | FC-PROTO-006, FC-SOL-003A | pinned fail-closed descriptor and descriptive discovery |
| SA-CHAN-001A | done | SA-CHAN-001, FC-PROTO-006, FC-SOL-003A | durable canonical operation commitment and conflict gate |
| SA-CHAN-001B | done | SA-CHAN-001A, FC-SOL-003A, FC-CTRL-036 | fixture-only v2 profile, funding identity, and common preparation contract |
| SA-CHAN-002 | ready | SA-CHAN-001, SA-CHAN-001A, SA-CHAN-001B, FC-SOL-003 | initialize/funding/activation fixture preparation |
| SA-CHAN-003 | ready | SA-CHAN-001, SA-CHAN-001A, SA-CHAN-001B, FC-SOL-003 | settlement fixture preparation |
| SA-CHAN-003A | blocked | SA-CHAN-001B, SA-CHAN-002, SA-CHAN-003 | binding and close/refund/finalization fixture preparation |
| SA-CHAN-004 | blocked | SA-CHAN-002, SA-CHAN-003 | inspect/status/recovery |
| SA-CHAN-005 | blocked | SA-CHAN-004, FC-PROTO-007 | channel evidence and conformance |

`SA-CHAN-001` through `SA-CHAN-005` execute in the independent Solana-Agent
repository under their own exact path contracts. The currently integrated
profiles remain fixture-only: handlers, signer access, RPC execution,
local-validator execution, Program ID publication, and all deployment
environments remain blocked.

## Epic F — Product and experience

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-PROD-001 | blocked | FC-VAL-003 | receive-link prototype |
| FC-PROD-002 | blocked | FC-SEC-003, FC-VAL-003 | protected claim-link prototype |
| FC-PROD-003 | blocked | FC-PROD-001, FC-PROD-002 | persistent-channel experience |
| FC-PROD-004 | blocked | FC-PROTO-003, FC-VAL-004 | recipient onboarding |
| FC-PROD-005 | blocked | FC-PROTO-004, SA-CHAN-003 | settlement/recovery experience |
| FC-PROD-006 | blocked | FC-PROTO-004 | receipts and sharing |

Product work does not become authorized merely because protocol prerequisites
exist. Validation and repository/privacy boundaries remain independent gates.

## Epic G — Validation

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-VAL-001 | blocked | FC-VAL-003 | interviews with stablecoin senders |
| FC-VAL-002 | blocked | FC-VAL-003 | interviews with stablecoin recipients |
| FC-VAL-003 | ready | FOUNDATIONS-001 | public 30-second comprehension protocol; human recruitment blocked by private/privacy gates |
| FC-VAL-004 | blocked | FC-PROD-002, FC-PROD-004 | claim-link and wallet-binding usability |
| FC-VAL-005 | blocked | FC-PROD-003 | repeated-channel reuse intent |

## Epic H — Offline failure validation

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-FAIL-003 | ready | FC-PROTO-004, FC-PROTO-005, SA-CHAN-000 | offline settlement/lifecycle failure lab without on-chain claims |

`FC-FAIL-003` validates only the controlled reference model. It cannot satisfy a
real-executor, deployed-program, Cloud-outage, devnet, or mainnet gate by
itself.

## Path ownership rule

The exact `allowed_paths`, invariants, acceptance tests, evidence requirements,
and stop conditions live in [`work-items.yaml`](work-items.yaml) and the
applicable task contract.

A `ready` item owns no path until activated. Two active items may not claim the
same mutable path. A cross-repository item must also satisfy the independent
repository's own authority surface before work begins there.

## Deployment rule

No sequence of `done` offline/model items implicitly releases deployment.
Operational ChannelVault implementation, local-validator execution, devnet,
mainnet, and real-value operation each require the explicit artifact/environment
authorization applicable at that boundary.
