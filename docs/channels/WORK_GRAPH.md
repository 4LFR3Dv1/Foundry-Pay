# Foundry Channels work graph

Status values: `blocked`, `ready`, `active`, `review`, `done`.

`FOUNDATIONS-001` owns architectural planning. Items marked `ready` may begin
after this foundation PR is merged without reopening accepted ADRs.

## Epic A — Control and decision

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-CTRL-001 | done | FOUNDATIONS-001 | program, thesis, scope, and non-goals |
| FC-CTRL-002 | done | FC-CTRL-001 | authority, state machines, and work graph |
| FC-CTRL-003 | done | FC-CTRL-001 | immutable baselines for both public repositories |
| FC-CTRL-004 | done | FC-CTRL-003 | reuse ledger and gap matrix |
| FC-CTRL-005 | done | FC-CTRL-001 | public/private and repository boundary |
| FC-CTRL-006 | done | FC-PROTO-001, FC-PROTO-002, FC-PROTO-003, FC-SEC-003 | reconcile integrated gates and unlock only satisfied offline work |
| FC-CTRL-007 | done | FC-PROTO-004 | record reviewed settlement integration and authorize FC-PROTO-005 paths |
| FC-CTRL-008 | done | FC-CTRL-007 | authorize the exact close-race vector migration required by FC-PROTO-005 |
| FC-CTRL-009 | done | FC-CTRL-008 | authorize migration of the foundation close-race checker to request/freeze snapshots |
| FC-CTRL-010 | done | FC-PROTO-005 | record reviewed close/refund integration and reconcile the graph |
| FC-CTRL-011 | done | FC-CTRL-010 | authorize normative documentation and provenance paths for FC-PROTO-006 |
| FC-CTRL-012 | done | FC-CTRL-011 | authorize the canonicalization test package marker |
| FC-CTRL-013 | done | FC-PROTO-006 | record reviewed canonicalization integration and reconcile the graph |
| FC-CTRL-014 | done | FC-CTRL-013 | freeze FC-PROTO-007 toolchains, runner contract, rejection matrix, independence, and paths |
| FC-GOV-001 | done | FC-CTRL-014 | separate work completion, evidence maturity, external review, and deployment authorization |
| FC-CTRL-015 | done | FC-PROTO-007, FC-GOV-001 | record governed conformance integration and reconcile the next security gate |
| FC-CTRL-016 | done | FC-CTRL-015, FC-GOV-001 | freeze FC-SEC-002 adversarial, lifecycle, maturity, and path contract |
| FC-CTRL-017 | done | FC-CTRL-016 | distinguish forbidden economic/authority effects from permitted rejection audit effects |
| FC-CTRL-018 | done | FC-CTRL-017 | align the FC-SEC-002 task contract dependency with the integrated effect taxonomy |
| FC-CTRL-019 | done | FC-SEC-002 | record self-validated security integration and release only satisfied experimental successors |
| FC-CTRL-020 | done | FC-CTRL-019, FC-SEC-002 | freeze the fixed-width FC-SOL-002 account-model contract |
| FC-CTRL-021 | done | FC-CTRL-019, SA-CHAN-000 | freeze the authority-free SA-CHAN-000 fake-adapter contract |
| FC-CTRL-022 | done | FC-SOL-002, SA-CHAN-000 | record account-model and fake-adapter integration |
| FC-CTRL-023 | done | FC-CTRL-022, FC-SOL-002, FC-SEC-002 | freeze the FC-SOL-003 instruction-contract boundary |
| FC-CTRL-024 | done | FC-SOL-003 | record instruction-contract integration and release satisfied successors |
| FC-CTRL-025 | done | FC-CTRL-024, FC-SOL-003 | freeze ABI implementability corrections before property testing or capability publication |
| FC-CTRL-026 | done | FC-SOL-003A | record operability correction and release satisfied successors |
| FC-CTRL-027 | done | FC-CTRL-026, FC-SOL-003A | freeze ownership-transition, settlement-correlation, and FC-SOL-004 validation semantics |
| FC-CTRL-028 | done | FC-CTRL-027, FC-SOL-003A | make historical manifest verification commit-aware before registry evolution |
| FC-CTRL-029 | done | FC-SOL-004 | record transition-model integration and release only satisfied offline work |
| FC-CTRL-030 | done | FC-CTRL-029, FC-SOL-004 | freeze offline concurrency, stale-snapshot, and linearization contract |
| FC-CTRL-031 | done | FC-SEC-004 | record concurrency integration without releasing runtime work |
| FC-CTRL-032 | done | FC-SEC-004, FC-SOL-003A | freeze governance, migration, and operation-identity preconditions |
| FC-CTRL-033 | done | FC-SOL-005 | record governance integration without authorizing deployment |
| FC-CTRL-034 | done | SA-CHAN-001 | record descriptive discovery and release only the operation-commitment gate |
| FC-CTRL-035 | done | SA-CHAN-001A | record operation-commitment integration and release only satisfied preparation contracts |

## Epic B — Channel protocol

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-PROTO-001 | done | FOUNDATIONS-001 | executable `Channel` and `ChannelFunding` validation |
| FC-PROTO-002 | done | FOUNDATIONS-001 | cumulative voucher verifier and monotonic reference ledger |
| FC-PROTO-003 | done | FOUNDATIONS-001 | claim and dual-signature recipient binding verifier |
| FC-PROTO-004 | done | FC-PROTO-001, FC-PROTO-002, FC-PROTO-003 | settlement and receipt implementation |
| FC-PROTO-005 | done | FC-PROTO-001, FC-PROTO-002 | close, expiry, epoch, and refund implementation |
| FC-PROTO-006 | done | FC-PROTO-001, FC-PROTO-002, FC-PROTO-003 | normative canonicalization and hashes |
| FC-PROTO-007 | done | FC-PROTO-006, FC-CTRL-014, FC-GOV-001 | self-validated Python/TypeScript/Rust cross-language conformance |

## Epic C — Security

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-SEC-001 | done | FOUNDATIONS-001 | comprehensive design threat model |
| FC-SEC-002 | done | FC-PROTO-002, FC-PROTO-006, FC-PROTO-007, FC-CTRL-017 | replay, semantic-collision, downgrade, and lifecycle property suite |
| FC-SEC-003 | done | FOUNDATIONS-001 | claim-link handling and secret non-disclosure test kit |
| FC-SEC-004 | done | FC-PROTO-004, FC-SOL-004, FC-CTRL-030 | offline concurrency and linearizability proof |
| FC-SEC-005 | blocked | FC-PROTO-004, SA-CHAN-004 | Cloud outage and self-recovery proof |

## Epic D — Solana program

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-SOL-001 | done | FOUNDATIONS-001 | ChannelVault design specification |
| FC-SOL-002 | done | FC-PROTO-001, FC-SEC-002 | fixed-width ChannelState PDA and classic SPL Token vault layout; local validator only |
| FC-SOL-003 | done | FC-PROTO-002, FC-PROTO-003, FC-PROTO-004, FC-PROTO-005, FC-SOL-002, FC-SEC-002 | atomic instruction, account-meta, exact Ed25519, lifecycle, event, and error contracts; local fixtures only |
| FC-SOL-003A | done | FC-SOL-003, FC-CTRL-025 | correct initialization metas; freeze permissionless settlement and bounded claim window |
| FC-SOL-004 | done | FC-SOL-003A, FC-SEC-002, FC-CTRL-027 | pure transition invariants with property-based and bounded exploration |
| FC-SOL-005 | done | FC-SOL-003A, FC-SEC-004, FC-CTRL-032 | upgrade, migration, rights-preservation, and governance policy |

No program implementation is authorized by `FOUNDATIONS-001`.

## Epic E — Solana-Agent

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| SA-CHAN-000 | done | FC-PROTO-007, FC-SEC-002, FC-CTRL-021 | draft capability contracts and adversarial fake adapter; offline fixture only, no ChannelVault compatibility claim |
| SA-CHAN-001 | done | FC-PROTO-006, FC-SOL-003A | pinned fail-closed ChannelVault descriptor and descriptive capability discovery |
| SA-CHAN-001A | done | SA-CHAN-001, FC-PROTO-006, FC-SOL-003A | durable canonical operation commitment and operation-ID conflict gate |
| SA-CHAN-002 | ready | SA-CHAN-001, SA-CHAN-001A, FC-SOL-003 | open/top-up/activation preparation |
| SA-CHAN-003 | ready | SA-CHAN-001, SA-CHAN-001A, FC-SOL-003 | settlement preparation |
| SA-CHAN-004 | blocked | SA-CHAN-002, SA-CHAN-003 | inspect/status/recovery |
| SA-CHAN-005 | blocked | SA-CHAN-004, FC-PROTO-007 | channel evidence and conformance |

`SA-CHAN-001` through `SA-CHAN-005` execute in the independent Solana-Agent
repository.

`SA-CHAN-000` is deliberately a public-protocol/fake-adapter precursor in
Foundry-Pay. Solana-Agent PR #14 independently completed `SA-CHAN-001` by
pinning the exact Foundry-Pay source commit and public registry bytes. The
result remains descriptive: it publishes no Program ID and reports
preparation, execution, status, recovery, and deployment support as false.

Solana-Agent PR #15 completed `SA-CHAN-001A`. It persists
`operation_id → canonical operation commitment`, distinguishes identical
replay, `OPERATION_CONFLICT`, and semantic alias conflict, and keeps stable
operation identity separate from exact ephemeral transaction-message bytes.
Only `SA-CHAN-002` and `SA-CHAN-003` become ready as preparation contracts.
Handlers, signer access, RPC execution, local-validator execution, and every
deployment environment remain blocked.

## Epic F — Product and experience

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-PROD-001 | blocked | FC-VAL-003 | receive-link prototype |
| FC-PROD-002 | blocked | FC-SEC-003, FC-VAL-003 | protected claim-link prototype |
| FC-PROD-003 | blocked | FC-PROD-001, FC-PROD-002 | persistent-channel experience |
| FC-PROD-004 | blocked | FC-PROTO-003, FC-VAL-004 | recipient onboarding |
| FC-PROD-005 | blocked | FC-PROTO-004, SA-CHAN-003 | settlement/recovery experience |
| FC-PROD-006 | blocked | FC-PROTO-004 | receipts and sharing |

Private product work uses the private Cloud repository. Public protocol
fixtures and UX contracts remain in Foundry-Pay.

## Epic G — Validation

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-VAL-001 | blocked | FC-VAL-003 | interviews with stablecoin senders |
| FC-VAL-002 | blocked | FC-VAL-003 | interviews with stablecoin recipients |
| FC-VAL-003 | ready | FOUNDATIONS-001 | 30-second proposition comprehension test |
| FC-VAL-004 | blocked | FC-PROD-002, FC-PROD-004 | claim-link and wallet-binding usability |
| FC-VAL-005 | blocked | FC-PROD-003 | repeated-channel reuse intent |

## Epic H — Offline failure validation

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FC-FAIL-003 | ready | FC-PROTO-004, FC-PROTO-005, SA-CHAN-000 | offline settlement/lifecycle failure lab without on-chain claims |

`FC-FAIL-003` validates only the controlled reference model. It cannot satisfy
`FC-SEC-004` or `FC-SEC-005`, whose on-chain and real-executor dependencies
remain unchanged.

## Initially completed foundation items

### FC-PROTO-001 — Channel and funding validator

- Repository: Foundry-Pay public
- Reserved paths:
  - `packages/channel-protocol/python/**`
  - `tests/channels/test_channel.py`
  - `contracts/channel/channel.schema.json`
  - work-item evidence/provenance
- Acceptance:
  - validate schema plus conservation and lifecycle semantics;
  - reject unknown fields, malformed amounts/addresses/time, and inconsistent
    totals;
  - no network, wallet, Cloud, or Solana program.

### FC-PROTO-002 — Cumulative voucher verifier

- Repository: Foundry-Pay public
- Reserved paths:
  - `packages/channel-protocol/python/**`
  - `tests/channels/test_voucher.py`
  - voucher vectors/evidence
- Acceptance:
  - compute deterministic payload hash;
  - verify sender signature through injected interface;
  - enforce epoch, previous hash, sequence, nondecreasing total, funding, and
    expiry;
  - prove stale/replayed vouchers add no reference-ledger effect.

### FC-PROTO-003 — Claim and recipient binding verifier

- Repository: Foundry-Pay public
- Reserved paths:
  - `packages/channel-protocol/python/**`
  - `tests/channels/test_recipient_binding.py`
  - claim/binding vectors/evidence
- Acceptance:
  - verify claim-key and destination-wallet signatures over identical bytes;
  - reject substitution, nonce replay, wrong channel/epoch/network/program;
  - implement initial binding only; rebind remains disabled.

### FC-SEC-003 — Claim-link security kit

- Repository: Foundry-Pay public
- Reserved paths:
  - `packages/channel-protocol/typescript/**`
  - `tests/channels/link-security/**`
  - `docs/channels/security/claim-link/**`
- Acceptance:
  - prove server request/log fixtures never contain fragment or claim private
    material;
  - validate locator entropy and uniform not-found behavior contract;
  - document browser/analytics/frontend residual risks without claiming human
    identity.

## Current protocol state

### FC-PROTO-004 — Settlement and receipt reference runtime (done)

- Repository: Foundry-Pay public
- Reserved paths:
  - `packages/channel-protocol/**`
  - `tests/channels/test_settlement.py`
  - `contracts/channel/settlement.schema.json`
  - `evidence/runs/FC-PROTO-004/**`
  - `provenance/REUSE_LEDGER.yaml`
- Scope: offline economic validation, exact execution correlation, durable
  recovery, and independently reconciled receipts.
- Explicitly unproven: Solana execution, ChannelVault behavior, consumer
  demand, and exactly-once blockchain execution.
- Reviewed head: `47a5c9f9160e5f0562058fd3e18936f24c222ab3`.
- Merge commit: `74359f6ac81e75d595f934ed3e03428a45a2dafa`.

### FC-PROTO-005 — Close, expiry, epoch, and refund semantics (done)

- Repository: Foundry-Pay public
- Scope: preserve unexpired rights during close and conservation during refund.
- Protocol v1 decision: activated rights do not expire economically and remain
  reserved until reconciled settlement.
- Reviewed functional head:
  `5e0737aefa6d707f6236f527950b845773bf26a5`.
- Final evidence head: `f39e3953692bb516745d7055ddd2c4f30775442a`.
- Merge commit: `59f37870475df0f0ee9d7619be9d3eff7f5a16bd`.
- Main CI run: `30231971193` (passed).
- Baseline must contain `74359f6ac81e75d595f934ed3e03428a45a2dafa`.
- Reserved paths:
  - `packages/channel-protocol/**`
  - `tests/channels/test_closure.py`
  - `contracts/channel/channel-closure.schema.json`
  - `contracts/channel/test-vectors/positive/close-race-v1.json`
  - `scripts/check_channel_foundation.py`
  - `tests/channels/test_foundation_contracts.py`
  - `docs/channels/ADR/FC-ADR-006-activated-right-expiry-v1.md`
  - `evidence/runs/FC-PROTO-005/**`
  - `provenance/REUSE_LEDGER.yaml`

### FC-PROTO-006 — Normative canonicalization

- Repository: Foundry-Pay public
- Scope: freeze signed-object domains only after the draft settlement objects
  exist.

### FC-PROTO-007 — Cross-language conformance

- Repository: Foundry-Pay public
- Coordination gate: `FC-CTRL-014`.
- Required implementations: Python, TypeScript, and Rust.
- Positive acceptance: identical canonical UTF-8 bytes, byte length, and
  SHA-256 in all three implementations.
- Negative acceptance: identical rejection stage and stable rejection code in
  all three implementations.
- Independence: each runner parses and computes from normative source inputs;
  no runner imports, invokes, generates, or reads another implementation.
- The comparator compares runner outputs only. It does not canonicalize,
  normalize, repair, or reinterpret a result.
- The functional work remains blocked until the coordination PR is integrated.

### FC-VAL-003 — 30-second comprehension test

- Repository: private product research; sanitized result in Foundry-Pay public
- Reserved public paths:
  - `docs/channels/validation/FC-VAL-003/**`
  - sanitized evidence only
- Acceptance:
  - at least five target users explain the proposition;
  - measure whether 10→25→40 is understood as 40, not 75;
  - measure understanding of funded, available, received, and remaining;
  - publish sanitized findings and decision changes.

## Gates

| Gate | Required before |
|---|---|
| schema + semantic validation | any reference implementation |
| canonical bytes + signature vectors | program or SDK signature verification |
| replay/domain property tests | settlement implementation |
| account/instruction contract | ChannelVault code |
| independent security review | devnet public pilot with meaningful funds |
| Cloud-free recovery proof | external adoption claim |
| upgrade governance and formal conservation assurance | any mainnet discussion |

## Unit of progress

```text
reviewed PR
+ green tests
+ generated evidence
+ recorded decision
+ preserved provenance
```
