# Foundry Channels program

- Program: Foundry Channels
- Foundation work item: `FOUNDATIONS-001`
- Status: architecture foundation in review
- Scope: public protocol and devnet MVP planning
- Date: 2026-07-24

## Executive summary

Foundry Channels turns a link from a one-time payment pointer into a persistent
relationship for transferring value. The first primitive is a unidirectional,
funded, cumulative channel that one sender can update and one recipient can
settle on demand.

The architecture has six strict authorities:

1. the sender creates economic intent and signs cumulative vouchers;
2. the public Foundry Channels protocol defines objects, hashes, invariants, and
   verification;
3. the future ChannelVault program enforces funding, monotonic activation,
   recipient binding, settlement, close, and refund on Solana;
4. a private Foundry Pay Cloud may resolve links, relay signed objects, notify,
   index, and orchestrate, but cannot manufacture rights;
5. Solana-Agent prepares, simulates, executes, confirms, recovers, and produces
   technical evidence under exact authorization;
6. a signer signs only the exact Solana message covered by a valid execution
   commitment.

The recommended safety decision is that an off-chain signed voucher is
`issued`, while only a voucher sequence recorded by ChannelVault is `activated`
and economically settleable. This is necessary because a verifier cannot know
that a newer off-chain voucher exists unless a monotonic authority observes it.
Activation may be relayed or sponsored, but requires the sender signature and
cannot be fabricated by the relay.

## Immutable baselines

| Repository | Commit | Role |
|---|---|---|
| `4LFR3Dv1/Solana-Agent` | `914eaf3c9b407f787c6f51d9886c6e86ae542335` | external Solana execution, recovery, and technical evidence |
| `4LFR3Dv1/Foundry-Pay` | `a8631b081f40029c18b16098508c44540efbf77f` | public protocol, authorization, reconciliation, conformance, and failure tooling |

The baselines are evidence inputs. No kernel is copied between repositories.

## Program objective

Produce an implementation-ready foundation in which:

- a channel and its rights can be explained independently of code;
- every authority and state transition has one owner;
- on-chain and off-chain state are explicitly separated;
- cumulative vouchers have domain separation and monotonic semantics;
- receive, claim, and persistent-channel links have different threat models;
- ambiguous broadcast outcomes stop and recover by signature;
- a minimal vertical slice can be built without reopening core decisions.

## First product proof

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

This is a target vertical slice, not a completed proof.

## MVP

Included:

- Solana devnet;
- one explicitly identified SPL fixture;
- one sender and one recipient;
- one-way funded channel;
- cumulative activated vouchers;
- partial or total settlement;
- top-up, expiry, close grace period, and refund;
- protected claim link and an existing recipient wallet;
- non-authoritative hosted relay;
- recovery by persisted signature;
- reproducible evidence.

Excluded:

- mainnet, custody, fiat, card, swaps, bridges, DEX, token issuance;
- bidirectional, multi-hop, cross-chain, or per-second streaming channels;
- a complete wallet or native mobile application;
- complex multi-tenancy, billing, automated compliance, or production SLAs.

## Product and security principles

- External-first: network execution remains outside Foundry Pay.
- Protocol-first: signed rights use closed, versioned, canonical objects.
- Hosted convenience, cryptographic right: the server may help find and
  deliver a right but may not create it.
- Monotonic cumulative state: authorized totals increase inside an epoch.
- Fail closed: uncertainty becomes `needs_recovery` or `needs_review`.
- Consumer-simple: the primary experience is “Open a channel. Share a link.
  Send as often as you want.”

## Current assets and gaps

Existing assets already cover exact-message execution authorization, durable
journals, signer isolation, replay rejection, status/recovery, source-diverse
reconciliation, failure injection, and evidence integrity.

The material gaps are:

- channel domain objects and canonical voucher bytes;
- ChannelVault accounts and instruction contract;
- on-chain cumulative sequence and conservation enforcement;
- claim-key and destination-wallet binding;
- close/refund treatment of outstanding recipient rights;
- channel-specific Solana-Agent capabilities;
- consumer and relay implementations.

See `INVENTORY.md` and `REUSE_MATRIX.md`.

## First milestone

The first implementation PR after this foundation should implement
`FC-PROTO-001`: executable validation for `Channel` and `ChannelFunding` against
the frozen schemas and fixtures in `contracts/channel/`. It must not contain a
program, Cloud service, wallet, or network call.

## Completion gates

Foundation completion requires:

- five accepted ADRs;
- internally consistent schemas and semantic test vectors;
- explicit authority and repository boundaries;
- state machines and a complete MVP flow;
- comprehensive threat model and adversarial review;
- a work graph with five execution-ready items;
- evidence tied to immutable baselines and validation commands.

It does not establish mainnet readiness, production safety, safe custody,
exactly-once blockchain execution, external audit, or proven scale.
