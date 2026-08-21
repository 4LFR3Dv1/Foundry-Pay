# Foundry Pay

Governed payment infrastructure for agent systems and stablecoin applications.

[![CI](https://github.com/4LFR3Dv1/Foundry-Pay/actions/workflows/ci.yml/badge.svg)](https://github.com/4LFR3Dv1/Foundry-Pay/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](pyproject.toml)
[![Status: pre-alpha](https://img.shields.io/badge/Status-pre--alpha-orange.svg)](ROADMAP.md)

Foundry Pay separates **economic authority** from **network execution**.
An application or agent system may request an economic action without becoming
an unrestricted wallet authority, controlling the signer, broadening the
recipient or amount, or blindly retrying an ambiguous transaction.

```text
request economic action
        ↓
validate economic intent and policy
        ↓
approve exact obligation
        ↓
prepare and simulate network operation
        ↓
authorize exact execution commitment
        ↓
sign only the authorized bytes
        ↓
broadcast once through a constrained executor
        ↓
recover if the outcome is ambiguous
        ↓
reconcile independent observations against the original obligation
        ↓
publish verifiable evidence
```

> Foundry Pay does not give an agent custody. It gives an application or agent
> system a governed way to request economic execution.

The public repository is an Apache-2.0 reference implementation and
proof-of-work. It is **not** a production custody system, a managed payment
service, or a claim of mainnet readiness.

## What is already demonstrated

The external-execution track has a complete public proof chain:

- governed SPL transfer on **Solana devnet**;
- short-lived, single-use **exact-message authorization**;
- signer boundary that accepts only the authorized serialized message;
- one controlled-runtime broadcast for the demonstrated transfer;
- signature-first persistence and recovery after ambiguous outcomes;
- source-diverse **L1/L2 reconciliation** through two live devnet RPC providers;
- deterministic and real-process failure matrices covering response loss,
  restart, RPC failure, concurrency, and recovery;
- sanitized, hash-bound evidence that separates demonstrated claims from open
  production gates.

The Foundry Channels track has also progressed beyond its initial foundation:

- channel accounting and funding validation;
- cumulative voucher verification and monotonic durable state;
- claim and dual-signature recipient binding;
- settlement, recovery, observation, and economic reconciliation;
- close, claim-window, refund, and epoch semantics;
- strict canonicalization with positive and adversarial vectors;
- independent Python, TypeScript, and Rust conformance runners;
- replay, semantic-collision, downgrade, and authority-boundary validation;
- fixed-width ChannelVault account model and instruction contracts;
- property-tested transition, concurrency, and upgrade-governance models;
- separate Solana-Agent discovery, operation-commitment, and fixture-only
  preparation boundaries.

These Channels results are deliberately scoped. There is **no deployed
ChannelVault program** and no claim of live channel funding, settlement,
mainnet readiness, or production custody.

## Start here if you are evaluating the project

You can understand the core claim in a few minutes without a wallet, RPC
endpoint, Solana CLI, token, or funds.

### 1. Run the local governance and recovery proof

```bash
git clone https://github.com/4LFR3Dv1/Foundry-Pay.git
cd Foundry-Pay
python -m venv .venv
```

Activate the environment:

```bash
# bash / zsh
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install and run:

```bash
python -m pip install -e .
python examples/local_proof.py
```

The proof prepares an exact message, issues a short-lived single-use
authorization, simulates a lost response after a durable effect, recovers the
receipt, and rejects replay.

Expected properties include:

```json
{
  "economic_effect_count": 1,
  "may_rematerialize": false,
  "recovery_outcome": "confirmed",
  "replay_blocked": true,
  "response_lost_after_commit": true
}
```

The full output includes hashes binding the economic plan, prepared message,
execution commitment, and receipt.

### 2. Inspect the public devnet transaction

The first governed end-to-end proof executed one approved SPL transfer of
`1,000,000` base units on Solana devnet.

- transaction:
  [`RzgQYATtgFZNG7eDgktPAaKh3R922BEjYNLRnvM7u96eFjsnSe4aFYQAtgaP4Hi7kyn91itF1eTEeo498NJ8uS4`](https://explorer.solana.com/tx/RzgQYATtgFZNG7eDgktPAaKh3R922BEjYNLRnvM7u96eFjsnSe4aFYQAtgaP4Hi7kyn91itF1eTEeo498NJ8uS4?cluster=devnet)
- slot: `478403722`
- source delta: `-1,000,000`
- destination delta: `+1,000,000`
- controlled gateway broadcasts for the demonstrated request: `1`

The transaction was then observed through two operationally distinct devnet
providers and reconciled against the original obligation.

Read the [external-execution evidence index](docs/EVIDENCE.md) for the exact
proof ledger, hashes, failure evidence, and claim boundaries.

### 3. Inspect the Channels work graph

The canonical [Foundry Channels work graph](docs/channels/WORK_GRAPH.md) records
what is done, ready, or blocked. It is intentionally stricter than a feature
checklist: work completion, self-validation, external review, and deployment
authorization are separate states.

The [Channels evidence index](docs/channels/EVIDENCE_INDEX.md) links integrated
protocol, security, Solana-model, and cross-repository milestones to their
commits and evidence.

## Why this is agent infrastructure

An agent may be allowed to request a `5 USDC` payment. That should not silently
imply authority to:

- change the recipient;
- increase the amount;
- select another asset;
- alter the network operation after approval;
- reuse an expired or consumed authorization;
- access unrestricted signing material;
- rebroadcast because an RPC response was lost;
- declare business success merely because a transaction receipt exists.

Foundry Pay makes those boundaries explicit.

Free-form prompts never cross the execution boundary. Economic intent becomes
structured, validated data; material execution is bound to exact commitments;
and a network receipt remains an evidence input until it is reconciled against
the original obligation.

That separation allows agent systems to participate in payment workflows
without making the agent, executor, or signer the final economic authority.

## Architecture

```text
Application / agent system
        │
        │ structured economic request
        ▼
┌────────────────────────────────────────────┐
│ Foundry Pay                                │
│ economic authority                         │
│                                            │
│ • obligation + policy                      │
│ • economic approval                        │
│ • exact execution authorization            │
│ • reconciliation                           │
│ • final business result                    │
└─────────────────────┬──────────────────────┘
                      │ exact commitment
                      ▼
┌────────────────────────────────────────────┐
│ Network-specific executor                  │
│ technical authority only                   │
│                                            │
│ • prepare / simulate                       │
│ • local safety policy                      │
│ • submit                                   │
│ • status / recovery                        │
│ • technical evidence                       │
└─────────────────────┬──────────────────────┘
                      │ exact authorized bytes
                      ▼
┌────────────────────────────────────────────┐
│ Signer boundary                            │
│                                            │
│ • validates authorization                  │
│ • validates exact message                  │
│ • signs no broader intent                  │
└─────────────────────┬──────────────────────┘
                      │
                      ▼
                  Blockchain
                      │
                      ▼
            independent observations
                      │
                      └──────────► Foundry Pay reconciliation
```

Foundry Pay owns:

- economic intent and global policy;
- economic approval and execution authorization;
- independent reconciliation and final business status.

A network-specific executor owns:

- network preparation and simulation;
- locally governed transmission;
- technical confirmation, status, recovery, and executor evidence.

A signer owns only the exact-byte signing boundary. It has no business
authority.

Read [Architecture](docs/ARCHITECTURE.md) and
[FP-ADR-001: external-first execution](docs/ADR/FP-ADR-001-external-first.md)
for the normative authority split.

## Canonical reconciliation flow

```text
observe divergence
→ create economic plan
→ approve plan
→ external executor prepares and simulates exact message
→ authorize exact execution commitment
→ signer validates and signs exact bytes
→ executor broadcasts once
→ recover if outcome is unknown
→ reconcile network observations against the obligation
→ publish hash-bound evidence
```

Objects are versioned and correlated by identifiers and hashes including
`execution_request_id`, `obligation_id`, `economic_plan_hash`,
`prepared_message_hash`, and `execution_commitment_hash`.

## Project surface

| Surface | Current public capability |
|---|---|
| External Execution Protocol | Versioned schemas, deterministic canonicalization, conformance vectors, exact commitments |
| Authorization | Short-lived, single-use grants bound to exact execution material |
| Signer boundary | Rejects changed, expired, consumed, or mismatched authorization/message material |
| Reconciliation | Source-diverse observations and deterministic economic outcomes |
| Failure and recovery | Response loss, restart, RPC failure, ambiguous outcome, concurrency, and recovery labs |
| Public evidence | Sanitized claim ledger, hashes, manifests, limitations, and residual gates |
| Foundry Channels protocol | Accounting, vouchers, binding, settlement, close/refund, canonicalization, durable offline runtime |
| Channels conformance | Python, TypeScript, and Rust exact-byte/rejection conformance |
| Channels security | Replay, semantic-collision, downgrade, link-secret, concurrency, and authority-boundary validation |
| ChannelVault modeling | Account layout, instruction contracts, transition invariants, concurrency, and upgrade-governance models |
| Solana-Agent integration | Separate capability discovery, operation commitments, and fixture-only preparation boundary |

## Foundry Channels

[Foundry Channels](docs/channels/PROGRAM.md) is the protocol-first design for
persistent, funded stablecoin transfer relationships:

> Open a channel. Share a protected link. Update cumulative value without
> giving a hosted service authority to manufacture recipient rights.

The normative economic relationship is:

```text
signed voucher = issued
ChannelVault acceptance = activated
activated total - settled total = liquidatable right
```

The public offline runtime may record `issued`, `verified`, and
`activation_requested`. It cannot declare a right `activated`; only a future
authoritative ChannelVault observation may establish that state.

### Current Channels maturity

| Area | Status |
|---|---|
| Protocol foundation | Integrated |
| Accounting / vouchers / binding / settlement / close-refund | Integrated offline runtime |
| Canonicalization | Frozen v1 profiles and adversarial vectors integrated |
| Python / TypeScript / Rust conformance | Integrated and self-validated |
| Replay / authority / concurrency security models | Integrated and self-validated |
| ChannelVault account and instruction contracts | Integrated models; no program deployment |
| Transition and upgrade-governance models | Integrated offline models |
| Solana-Agent Channels bridge | Discovery, operation commitment, and fixture-only preparation boundary integrated |
| Transaction handlers / signer / RPC Channels execution | Blocked |
| Local-validator / devnet / mainnet Channels deployment | Blocked |
| Hosted consumer product | Not claimed |
| External user adoption / product demand | Not established |

For exact dependency and authorization state, use the
[work graph](docs/channels/WORK_GRAPH.md), not this summary.

### Run the Channels protocol suite

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/channels
npm ci --prefix packages/channel-protocol/typescript
npm test --prefix packages/channel-protocol/typescript
```

The suite covers:

- conservation and lifecycle rules for funding;
- monotonic cumulative vouchers and replay rejection;
- claim and destination-wallet binding;
- partial and total settlement, idempotency, restart, and recovery;
- technical execution versus economic reconciliation;
- close-window, refund, activated-right, and epoch-transition rules;
- strict canonicalization, domain separation, Unicode, and numeric boundaries;
- claim-link secret handling in the TypeScript surface;
- cross-language exact-byte and rejection behavior;
- adversarial authority and concurrency properties.

## Reference executor: Solana-Agent

[Solana-Agent](https://github.com/4LFR3Dv1/Solana-Agent) is the first separate
reference consumer of the External Execution Protocol. It remains an
independently installable Apache-2.0 public good and is not imported as Foundry
Pay's kernel.

This separation is intentional:

```text
Foundry Pay                    Solana-Agent
economic authority             network specialist
------------------             ------------------
obligation                     prepare / simulate
approval                       Solana policy
exact authorization    ─────►  execute
reconciliation                 status / recover
economic result      ◄───────  technical evidence
```

Executor receipts are evidence inputs, not declarations of business success.

## Failure and recovery model

An unknown broadcast result does **not** become an assumed failure.

Foundry Pay never automatically materializes or broadcasts a replacement while
an earlier obligation may already have executed. The controlled path enters
`needs_recovery` and resolves the earlier attempt first.

The public failure suites cover:

- failure before signature persistence;
- restart after signature persistence;
- response loss after broadcast acceptance;
- blockhash expiry and definitive RPC rejection;
- repeated and concurrent recovery attempts;
- source unavailability and later reconciliation convergence.

The canonical real-process scenario proves:

```text
upstream accepts transaction
→ response is lost
→ runtime enters needs_recovery
→ runtime restarts
→ recovery finds the committed transaction
→ confirmed without rebroadcast
```

Read [Failure recovery](docs/FAILURE_RECOVERY.md),
[Process chaos](docs/PROCESS_CHAOS.md), and the
[evidence index](docs/EVIDENCE.md).

## Who it is for

- agent and application developers that need bounded payment execution;
- stablecoin and payment teams designing controlled remediation;
- wallet, custody, and treasury engineers evaluating signer/authority splits;
- network-executor developers implementing a constrained execution protocol;
- security and reliability engineers testing ambiguous transaction outcomes;
- protocol contributors working on schemas, conformance, recovery, and
  verifiable evidence.

## Development

Install development dependencies:

```bash
python -m pip install -e ".[dev]"
npm ci --prefix packages/external-execution-protocol/typescript
```

Run the core checks used by CI:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
npm test --prefix packages/external-execution-protocol/typescript
```

Repository governance, work-item contracts, path reservations, evidence
requirements, and authority gates are documented in [AGENTS.md](AGENTS.md), the
[external-execution work graph](docs/WORK_GRAPH.md), and the
[Channels work graph](docs/channels/WORK_GRAPH.md).

These are maintainer controls, not prerequisites for running the five-minute
proof.

## Current status and claim boundary

Foundry Pay is **pre-alpha**.

### Demonstrated

- governed exact-message payment execution on Solana devnet;
- one-broadcast controlled execution for the published end-to-end proof;
- recovery without blind rebroadcast after ambiguous outcomes;
- source-diverse reconciliation;
- public protocol, security, failure, and evidence tooling;
- substantial offline Foundry Channels protocol and Solana-program modeling.

### Not claimed

- production or mainnet readiness;
- arbitrary-failure or exactly-once blockchain execution;
- production HSM/MPC custody;
- externally audited security;
- deployed ChannelVault behavior;
- live Channels funding, activation, settlement, close, or refund;
- hosted consumer product readiness;
- proven external user comprehension, adoption, or demand.

The project deliberately separates:

```text
work item delivered
≠ self-validation passed
≠ external review passed
≠ deployment authorized
≠ production ready
```

That distinction is part of the protocol's governance model, not a disclaimer
added after the fact.

See the public [roadmap](ROADMAP.md),
[external-execution evidence](docs/EVIDENCE.md),
[Channels evidence](docs/channels/EVIDENCE_INDEX.md), and
[Channels work graph](docs/channels/WORK_GRAPH.md).

## Contributing and external verification

External verification is one of the most useful contributions to the project.
You can help without a wallet or funds by:

1. cloning the repository in a clean environment;
2. running `python examples/local_proof.py`;
3. running the public protocol tests;
4. independently inspecting one evidence pack or public devnet proof;
5. opening an issue with the exact environment, commands, and result.

For code contributions, read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md).

Do not report vulnerabilities through a public issue. Follow
[SECURITY.md](SECURITY.md) and use GitHub's private vulnerability reporting
channel.

## Public and commercial boundary

The public protocol, reference implementations, deterministic services, tests,
documentation, sanitized fixtures, and evidence are Apache-2.0 open source.

Production credentials, customer data, custody and key infrastructure, private
risk rules, proprietary connectors, deployment configuration, and managed
operations are not included in this repository.

This architectural boundary does not narrow the Apache-2.0 rights granted for
public code. Read the complete
[public/commercial boundary](docs/PUBLIC_COMMERCIAL_BOUNDARY.md) and
[FP-ADR-002](docs/ADR/FP-ADR-002-open-source-boundary.md).

## License

Foundry Pay content for which the licensor holds the necessary rights is
licensed under the [Apache License 2.0](LICENSE). Copyright attribution is in
[NOTICE](NOTICE). Third-party materials retain their respective licenses and
attribution requirements; see
[third-party notices](provenance/THIRD_PARTY_NOTICES.md).
