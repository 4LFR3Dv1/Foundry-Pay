# Foundry Channels work graph

This is the human-readable execution-authority surface for Foundry Channels.
It answers one question:

> What work is currently integrated, blocked, ready, or active?

Strategic priority lives in the repository Roadmap. Demonstrated claims and
maturity live in the evidence indexes.

Status values are `blocked`, `ready`, `active`, `review`, and `done`.

```text
work item delivered
!= self-validation passed
!= external review passed
!= deployment authorized
!= production/mainnet ready
```

## Authority registries

- [`work-items.yaml`](work-items.yaml) — historical/current protocol, model,
  security, validation, and pre-beta Solana-Agent work;
- [`beta/work-items.yaml`](beta/work-items.yaml) — operational public-beta
  campaign authorized by `FC-ADR-010`.

The beta registry may release capabilities only where an explicit beta ADR or
work item grants that authority. It does not rewrite historical evidence.

## Current frontier

| Work item | Status | Repository | Capability |
|---|---|---|---|
| FC-BETA-001 | active | `4LFR3Dv1/Foundry-Channels` | public web/API runtime, fail-closed over authoritative state |
| FC-SOL-003B | active | `4LFR3Dv1/Foundry-Pay` | close signed-preimage + initialization runtime operability gap |
| FC-SOL-006 | blocked | `4LFR3Dv1/Foundry-Pay` | operational ChannelVault; waits on FC-SOL-003B |
| SA-CHAN-002 | ready | `4LFR3Dv1/Solana-Agent` | initialize/funding/activation preparation |
| SA-CHAN-003 | ready | `4LFR3Dv1/Solana-Agent` | settlement preparation |
| FC-FAIL-003 | ready | `4LFR3Dv1/Foundry-Pay` | offline settlement/lifecycle failure lab |
| FC-BETA-002 | blocked | multi-repository | end-to-end real Solana devnet certification |
| FC-OPS-001 | blocked | `4LFR3Dv1/Foundry-Channels` | production deployment + custom domain |

The product may advance in parallel, but unavailable economic capabilities must
remain visibly unavailable. No fixture data may substitute for missing chain or
runtime authority.

## Public beta authority

`FC-GOV-002` / `FC-ADR-010` authorizes a real operational beta on
**Solana devnet** with this topology:

```text
Foundry-Pay
  protocol + economic authority + ChannelVault
          |
          v
Solana-Agent
  preparation + execution + status + recovery
          |
          v
Foundry-Channels
  public web/API + durable product state
```

The beta may use real wallets, a real devnet program, real devnet transactions,
durable Postgres state, recovery/reconciliation, Railway, and a custom domain
after certification.

It does not authorize Solana mainnet, real-value production claims, user-wallet
custody, Celo/EVM, another network, production HSM/MPC claims, or PMF claims.

## Integrated baseline

Historical registry/evidence records the exact items. The integrated baseline
includes:

- `FC-PROTO-001..007` — accounting, cumulative vouchers, recipient binding,
  settlement/recovery, close/refund, canonicalization and cross-language
  conformance;
- `FC-SEC-001..004` — threat model, adversarial protocol tests, claim-link
  handling and offline concurrency evidence;
- `FC-SOL-001..005` plus `FC-SOL-003A` — 490-byte ChannelState, v1 instruction
  and Ed25519 transport contracts, transition model and governance;
- `SA-CHAN-000..001B` — capability contracts, descriptor, operation commitment,
  funding identity and fixture preparation boundary.

These remain protocol/model evidence, not deployment evidence.

## Runtime operability correction — FC-SOL-003B

The first `FC-SOL-006` implementation pass exposed a real mismatch between the
frozen transport contract and the exact FC-PROTO-006 signer authority.

The v1 `activate_voucher` args do not contain every field present in the exact
sender-signed canonical payload. The same is true for recipient binding, and
`initialize_channel` does not provide all immutable identity fields needed to
validate those payloads later.

Therefore `FC-SOL-006` is blocked until `FC-SOL-003B` is integrated.

`FC-SOL-003B` must preserve:

```text
ChannelState layout            490 bytes, unchanged
PDA seeds                      unchanged
FC-PROTO-006 signed bytes      unchanged
operation registry             8 names, unchanged
Ed25519 precompile layout      unchanged
historical instruction v1     byte-reproducible
```

It introduces an explicit runtime instruction version instead of silently
changing v1. The runtime consumes the exact canonical message bytes from the
immediately preceding Ed25519 instruction, validates their canonicality/hash,
and binds every authority-bearing field to current state/instruction context.
See
[`solana/instructions/FC-SOL-003B-RUNTIME-PREIMAGE-CORRECTION.md`](solana/instructions/FC-SOL-003B-RUNTIME-PREIMAGE-CORRECTION.md).

## ChannelVault runtime gate — FC-SOL-006

After `FC-SOL-003B`, `FC-SOL-006` may implement the first real ChannelVault
entrypoint and handlers while preserving:

```text
ChannelState space       490 bytes
network                  Solana
first beta environment   devnet
asset program            classic SPL Token only
operations               8, closed registry
```

The operations remain:

1. `initialize_channel`
2. `fund_channel`
3. `activate_voucher`
4. `bind_recipient`
5. `settle`
6. `request_close`
7. `refund_unallocated`
8. `finalize_close`

Local-validator execution belongs to `FC-SOL-006` evidence. Devnet deployment
requires a later exact-artifact/Program-ID authorization after that evidence is
reviewed.

## Product runtime gate — FC-BETA-001

`FC-BETA-001` owns `4LFR3Dv1/Foundry-Channels`.

Consumer-visible economic state is forbidden unless it traces to authoritative
runtime state:

```text
no Program ID
or no RPC
or no durable database
or wrong program owner
or invalid ChannelState bytes
        => fail closed
```

No fixture, hard-coded example, seeded balance, fake transaction, or synthetic
chain observation may keep a consumer flow apparently operational.

Wallet secret material stays client-controlled. Hosted infrastructure may only
prepare, persist, relay, observe, reconcile and recover within its exact
work-item authority.

## Solana-Agent path

```text
SA-CHAN-002  initialize / funding / activation preparation
        \
         +--> SA-CHAN-003A  binding / close / refund / finalization
        /
SA-CHAN-003  settlement preparation
                 |
                 v
          SA-CHAN-004  inspect / status / recovery
                 |
                 v
          SA-CHAN-005  evidence / conformance
```

Preparation does not itself authorize RPC execution. The Solana-Agent
repository must release its own runtime authority before the beta uses a live
operation.

## Certification and deployment

`FC-BETA-002` targets one real end-to-end Solana devnet proof:

```text
real sender wallet
-> initialize ChannelVault
-> fund channel
-> activate cumulative value
-> recipient claim + wallet binding
-> partial/full settlement
-> ambiguous-response recovery without blind retry
-> independent reconciliation
-> close/refund/finalize boundary
-> reproducible multi-repository evidence
```

Only after certification may `FC-OPS-001` attach the operational custom domain.
Engineering preview deployments may exist earlier but are not the certified
public beta.

## Product validation

`FC-VAL-003` remains a valid comprehension protocol but is no longer a
prerequisite for beta implementation. Comprehension/usability should be tested
against the operational beta.

Human recruitment remains separately blocked until private research storage,
consent, privacy review, and immutable-run-manifest requirements are satisfied.
Building the beta does not prove comprehension, repeated use, or demand.

The historical `FC-PROD-*` prototype sequence remains historical; the public
beta is governed by `FC-BETA-*`.

## Evidence, ownership, and deployment

Historical evidence remains in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md). Beta
evidence is added only after the corresponding real capability is observed.

Exact paths, tests, invariants and stop conditions live in the governing
registry/task contract. `ready` owns no path until activated. Cross-repository
work must satisfy the authority surface of the repository where it executes.

The operational ladder is:

```text
contract correctness
-> implementation
-> local execution evidence
-> exact artifact authorization
-> devnet deployment
-> end-to-end devnet certification
-> production-hosted beta + custom domain
```

None of those steps implies mainnet or real-value authority.
