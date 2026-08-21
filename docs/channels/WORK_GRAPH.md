# Foundry Channels work graph

This is the human-readable execution-authority surface for Foundry Channels.
It answers one question:

> What work is currently integrated, blocked, ready, or active?

It does not define strategic priority or evidence maturity. Those remain in the
repository Roadmap and evidence indexes.

Status values are `blocked`, `ready`, `active`, `review`, and `done`.

```text
work item delivered
!= self-validation passed
!= external review passed
!= deployment authorized
!= production/mainnet ready
```

## Authority registries

Foundry Channels now has two explicit work registries:

- [`work-items.yaml`](work-items.yaml) — historical/current protocol, model,
  security, validation, and pre-beta Solana-Agent work;
- [`beta/work-items.yaml`](beta/work-items.yaml) — the operational public-beta
  campaign authorized by `FC-ADR-010`.

The beta registry may release capabilities only where
[`ADR/FC-ADR-010-public-beta-devnet.md`](ADR/FC-ADR-010-public-beta-devnet.md)
explicitly grants that authority. It does not rewrite historical evidence.

## Current frontier

| Work item | Status | Repository | Capability |
|---|---|---|---|
| FC-BETA-001 | active | `4LFR3Dv1/Foundry-Channels` | public web/API beta runtime, fail-closed over authoritative state |
| FC-SOL-006 | ready | `4LFR3Dv1/Foundry-Pay` | promote frozen ChannelVault models into an operational Solana program |
| SA-CHAN-002 | ready | `4LFR3Dv1/Solana-Agent` | initialize/funding/activation preparation |
| SA-CHAN-003 | ready | `4LFR3Dv1/Solana-Agent` | settlement preparation |
| FC-FAIL-003 | ready | `4LFR3Dv1/Foundry-Pay` | offline settlement/lifecycle failure lab |
| FC-BETA-002 | blocked | multi-repository | end-to-end real Solana devnet certification |
| FC-OPS-001 | blocked | `4LFR3Dv1/Foundry-Channels` | production deployment + custom domain |

`FC-BETA-001` is allowed to build the real product in parallel with program and
executor work, but consumer actions must remain fail-closed until the exact
runtime capability exists. It may not substitute fixture data for unavailable
chain state.

## Public beta decision

`FC-GOV-002` / `FC-ADR-010` changes the product sequencing deliberately.
Foundry Channels is now authorized to become a public operational beta on
**Solana devnet**.

The topology is:

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

The beta may use real wallets, a real deployed devnet program, real devnet
transactions, durable Postgres state, recovery, reconciliation, Railway, and a
custom public domain after certification.

The beta may **not** infer authority for:

- Solana mainnet;
- real-value production claims;
- custody of user wallet secret material;
- a second blockchain/network;
- Celo/EVM execution;
- production HSM/MPC claims;
- product-market-fit claims.

A production-hosted beta and a mainnet/value-production authorization are
separate facts.

## Integrated protocol/model baseline

The historical registry and evidence index record the exact individual items.
The integrated baseline includes:

- `FC-PROTO-001..007` — channel accounting, funding, cumulative vouchers,
  recipient binding, settlement/recovery, close/refund, canonicalization, and
  Python/TypeScript/Rust conformance;
- `FC-SEC-001..004` — threat model, adversarial protocol tests, claim-link
  secret handling, and offline concurrency/linearizability evidence;
- `FC-SOL-001..005` plus `FC-SOL-003A` — the frozen 490-byte ChannelState,
  instruction/Ed25519 contracts, transition model, concurrency preconditions,
  governance, migration, and rights-preservation policy;
- `SA-CHAN-000..001B` — capability contracts, pinned descriptor, durable
  operation commitments, funding identity, and fixture-only preparation
  boundary.

These integrated items remain model/protocol evidence. They are not silently
relabeled as deployed evidence by the beta decision.

## ChannelVault runtime gate

`FC-SOL-006` is the first work item allowed to implement a real ChannelVault
entrypoint and economic handlers.

It must preserve the existing frozen inputs:

```text
ChannelState space       490 bytes
network                  Solana
first beta environment   devnet
asset program            classic SPL Token only
v1 operations            8, closed registry
```

The eight operations remain:

1. `initialize_channel`
2. `fund_channel`
3. `activate_voucher`
4. `bind_recipient`
5. `settle`
6. `request_close`
7. `refund_unallocated`
8. `finalize_close`

Local-validator execution belongs to `FC-SOL-006` evidence. A devnet deployment
must be bound to an exact built artifact and Program ID before it can feed the
beta certification gate.

## Product runtime gate

`FC-BETA-001` owns the new public product repository.

Consumer-visible economic state is forbidden unless it can be traced to the
configured authoritative runtime. In particular:

```text
no Program ID
or no RPC
or no durable database
or wrong program owner
or invalid ChannelState bytes
        => fail closed
```

No fixture, hard-coded example, seeded balance, fake transaction, or synthetic
chain observation may be used to keep a consumer flow apparently operational.

Wallet secret material remains client-controlled. Hosted infrastructure may
prepare, persist, relay, observe, reconcile, and recover only within its exact
work-item authority.

## Solana-Agent path

The pre-beta Solana-Agent sequence remains:

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

Preparation work does not itself authorize RPC execution. The Solana-Agent
repository must release its own runtime/execution authority before a live beta
operation uses it.

## Certification and deployment

`FC-BETA-002` remains blocked until the exact dependencies in the beta registry
are integrated. Its target is a real end-to-end Solana devnet proof:

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

Only after that certification may `FC-OPS-001` attach the operational public
custom domain.

Engineering preview deployments may exist earlier, but they must not be
presented as the certified public beta.

## Product validation

`FC-VAL-003` remains a valid comprehension protocol, but it is no longer a
prerequisite for all beta implementation. The explicit product decision is to
validate comprehension/usability against the operational beta.

Human recruitment is still separately blocked until its private research
storage, consent, privacy-review, and immutable-run-manifest requirements are
satisfied. Building the beta does not waive those privacy gates and does not
prove comprehension, repeated use, or demand.

The historical `FC-PROD-*` prototype sequence remains historical/blocked under
the old registry. The public beta is governed by `FC-BETA-*` instead of silently
changing those old records.

## Evidence and path ownership

Historical evidence remains in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md).
Beta evidence must be added only after the corresponding real capability is
observed.

Exact paths, invariants, acceptance criteria, tests, and stop conditions live in
the governing registry/task contract.

A `ready` item owns no path until activated. Two active items must not own the
same mutable path. A cross-repository item must also satisfy the authority
surface of the repository where it executes.

## Deployment rule

The operational ladder is explicit:

```text
implementation
-> local execution evidence
-> exact artifact authorization
-> devnet deployment
-> end-to-end devnet certification
-> production-hosted beta + custom domain
```

None of those steps implies mainnet or real-value authority.
