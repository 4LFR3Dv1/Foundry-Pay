# Foundry Pay Program

## Mission

Foundry Pay is governed payment infrastructure for stablecoin systems and
agentic applications. Its core rule is that requesting an economic action does
not grant a network executor authority to invent, broaden, or reinterpret that
action.

Foundry Pay owns economic intent, approval, exact execution authorization,
independent reconciliation, and the final business result. Network-specific
executors remain independent and own preparation, simulation, transmission,
technical confirmation, recovery, and technical evidence under bounded
authority.

## Current baseline

The original External Execution proof milestone has been achieved on Solana
devnet. The public evidence includes:

- versioned protocol objects and canonicalization;
- short-lived, single-use exact-message authorization;
- an isolated signer boundary;
- one governed SPL transfer on Solana devnet;
- source-diverse reconciliation;
- deterministic and real-process recovery/failure evidence.

See [`EVIDENCE.md`](EVIDENCE.md) for the exact demonstrated boundary and
non-claims.

Foundry Channels has also progressed beyond its architecture foundation. The
public repository now contains an integrated offline protocol/model baseline,
security and concurrency work, ChannelVault account/instruction/transition
models, and Solana-Agent fixture-preparation contracts. That work does not mean
an operational ChannelVault exists or that any deployment is authorized.

## Program tracks

### 1. External Execution

The first network proof exists. The current protocol-stabilization frontier is:

- errors, capabilities, and version negotiation (`FP-PROTO-004`);
- correlated journal and evidence-manifest contracts (`FP-PROTO-005`);
- simulation validity and drift handling (`FP-PROTO-006`);
- external verification by developers who did not build the system.

The top-level execution state is governed by [`WORK_GRAPH.md`](WORK_GRAPH.md).

### 2. Foundry Channels

Foundry Channels explores persistent funded transfer relationships:

> Open a channel. Share a link. Send as often as you want.

Its detailed execution authority is delegated to
[`channels/WORK_GRAPH.md`](channels/WORK_GRAPH.md) and
[`channels/work-items.yaml`](channels/work-items.yaml).

The current technical frontier is to complete network-executor preparation,
settlement preparation, status/recovery, and evidence/conformance boundaries
before any operational ChannelVault is authorized.

Human proposition validation is a strategic priority, but the public protocol
does not authorize recruitment. The private research-storage, consent,
privacy-review, and immutable-run-manifest gates must be established first.

### 3. Operational ChannelVault

A real ChannelVault implementation is a later capability, not current execution
authority. Moving from models/fixtures to operational handlers requires a new
explicit governance decision. Local-validator or devnet execution requires the
applicable artifact/environment authorization; mainnet and real value remain
separate later gates.

### 4. Network independence

After the execution boundary is externally understandable and the Channels
frontier is sufficiently closed, a second independently implemented blockchain
execution environment should test whether Foundry Pay is genuinely
network-independent rather than a Solana-shaped abstraction.

An EVM environment is a candidate future lane. No EVM network, including Celo,
is authorized by this program document alone.

## Strategic order

The current direction is maintained in [`../ROADMAP.md`](../ROADMAP.md). At the
program level the intended progression is:

```text
external verification + human validation
-> stabilize public execution protocol
-> complete Channels execution boundaries
-> explicitly authorize operational ChannelVault work
-> prove the controlled devnet vertical slice
-> prove a second network execution environment
-> satisfy independent production gates before production claims
```

This ordering is strategic direction, not automatic execution authority.

## Authority model for repository state

The repository keeps four public questions separate:

| Question | Authority |
|---|---|
| What is this project? | `README.md` |
| What should become true next, and why? | `ROADMAP.md` |
| What has actually been demonstrated? | `docs/EVIDENCE.md` |
| What work may start or owns paths? | governing work graph + task contract |

Foundry Channels has its own delegated graph and evidence index. Top-level
documentation must not mirror child statuses in a way that creates two owners
for the same execution decision.

## Production boundary

Nothing in this program document claims:

- production custody or signer operations;
- an operational or deployed ChannelVault;
- live Foundry Channels funding, activation, settlement, close, or refund;
- mainnet readiness;
- independent security audit where none is recorded;
- proven product demand or independent adoption;
- exactly-once blockchain execution;
- universal multi-chain support.

Work-item completion, self-validation, external review, deployment
authorization, and production readiness remain separate facts.
