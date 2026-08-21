# FC-ADR-010 — Public operational beta on Solana devnet

Status: accepted by explicit human product authority, pending integration of this coordination change.

## Context

Foundry Channels has a mature offline protocol/model baseline but no operational ChannelVault program, public consumer application, or deployed channel execution environment. The prior roadmap sequenced human comprehension validation before product implementation.

The product authority has explicitly changed that strategy: Foundry Channels should become a public beta application with its own domain and real execution. `beta` describes product maturity; it does not permit mocked balances, fixture-backed consumer state, or synthetic blockchain execution.

## Decision

Authorize a new bounded public-beta campaign with the following topology:

```text
4LFR3Dv1/Foundry-Pay
  protocol + economic authority + ChannelVault implementation/evidence

4LFR3Dv1/Solana-Agent
  Solana preparation + execution + status + recovery

4LFR3Dv1/Foundry-Channels
  public web/API product + durable application state
```

The first operational network is `solana:devnet`.

The campaign may implement a real ChannelVault program, execute it on local validator, deploy an exact certified artifact to Solana devnet, operate a public web/API beta, persist channel/claim/operation correlation, connect real user wallets, and expose authoritative channel state.

## Production versus mainnet

A production web deployment and a mainnet/value-production authorization are different facts.

This ADR permits a production-hosted beta whose economic execution remains on Solana devnet. It does **not** authorize:

- Solana mainnet;
- real-value production claims;
- production custody;
- hosted wallet private keys or seed material;
- HSM/MPC custody claims;
- a second blockchain network;
- Celo/EVM execution;
- product-market-fit claims.

## Consumer-state rule

No consumer-visible economic state may originate from a mock, fixture, seed object, hard-coded example, or synthetic chain response.

A Channel view may render only when its state can be traced to:

1. an authorized ChannelVault Program ID;
2. an account owned by that program;
3. a structurally valid frozen `ChannelState` layout;
4. durable application correlation where Cloud state is required;
5. the exact network/environment configured for the beta.

If those conditions are not satisfied, the application fails closed.

## Wallet and custody rule

Wallet authority remains client-controlled. A hosted Foundry Channels service may prepare, relay, persist, inspect, reconcile, and recover according to its work item, but it must not require a wallet seed phrase or private key.

Program deployment authority is a separate operational secret and must never be committed to a public repository.

## ChannelVault promotion

The existing `foundry-channel-vault-account-model` and instruction/transition/governance crates are frozen inputs. A new work item, `FC-SOL-006`, is authorized to promote those inputs into a real Solana program.

The implementation must preserve:

- the exact 490-byte v1 `ChannelState` layout;
- deterministic PDA derivation;
- classic SPL Token only;
- the closed eight-operation v1 registry;
- exact Ed25519-precompile semantics;
- transition, conservation, concurrency, and governance invariants.

Local-validator execution is part of implementation evidence. Devnet deployment requires an exact-artifact authorization after that evidence exists.

## Product work

`FC-BETA-001` is authorized immediately in `4LFR3Dv1/Foundry-Channels`. It may build the public application and integration boundaries in parallel with ChannelVault runtime work, but user actions must stay disabled/fail-closed until their real program/executor capabilities exist.

This supersedes the earlier sequencing assumption that all product implementation must wait for `FC-VAL-003`. Human comprehension and usability validation should be performed against the operational beta. This change does not convert product implementation into evidence of comprehension or demand.

## Deployment gate

Attaching the production custom domain is `FC-OPS-001` and remains blocked until `FC-BETA-002` certifies the end-to-end real devnet flow. A Railway preview/internal deployment may be used for engineering, but it must not be presented as the operational public beta before certification.

## Authority registry

The new beta campaign is governed by `docs/channels/beta/work-items.yaml`. The historical `docs/channels/work-items.yaml` remains authoritative for the existing protocol/model work items. When an ID exists in both registries during migration, the beta registry may only narrow or advance authority where this ADR explicitly says so; it may not silently rewrite historical evidence.

## Consequences

The immediate production frontier becomes:

```text
FC-BETA-001 web/API runtime       (active)
FC-SOL-006 ChannelVault runtime   (ready)
SA-CHAN-002 + SA-CHAN-003         (ready in Solana-Agent lane)
        ↓
remaining executor/recovery gates
        ↓
FC-BETA-002 devnet certification
        ↓
FC-OPS-001 production domain
```

Mainnet remains a separate later decision.
