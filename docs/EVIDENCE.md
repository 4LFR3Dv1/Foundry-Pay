# Foundry Pay evidence index

This document is the top-level claim boundary for the public Foundry Pay
repository. It separates what has been demonstrated on a live blockchain from
what has been demonstrated in deterministic runtimes, offline protocol models,
and cross-repository integration fixtures.

Work-item completion, self-validation, external review, deployment
authorization, and production readiness are different states. Evidence in this
repository must not be read as authority to broaden any of those claims.

## Evidence tracks

Foundry Pay currently has two related but distinct evidence tracks.

### External Execution

This track demonstrates governed payment execution through an independent
network executor. It includes exact-message authorization, signer isolation,
one controlled broadcast, recovery after ambiguous outcomes, live Solana
devnet settlement, source-diverse reconciliation, and deterministic failure
labs.

### Foundry Channels

This track develops the protocol and security model for persistent funded
stablecoin transfer relationships. Its current evidence includes offline
accounting, cumulative vouchers, recipient binding, settlement/recovery,
close/refund semantics, cross-language canonicalization, adversarial security
validation, ChannelVault account/instruction/transition/governance models, and
fixture-only Solana-Agent integration.

Foundry Channels does **not** currently prove a deployed ChannelVault, live
channel funding or settlement, signer/RPC execution, a hosted consumer product,
or mainnet readiness.

The detailed Channels ledger is maintained in
[`docs/channels/EVIDENCE_INDEX.md`](channels/EVIDENCE_INDEX.md). The canonical
ready/blocked execution state is maintained separately in
[`docs/channels/WORK_GRAPH.md`](channels/WORK_GRAPH.md).

## Evidence classes

| Class | What it can prove | What it cannot prove |
|---|---|---|
| Live-chain evidence | A specific transaction and observed chain state existed on the named network | Mainnet readiness, production safety, or universal protocol correctness |
| Deterministic runtime evidence | Exact protocol/runtime behavior under controlled inputs and faults | Real-chain behavior outside the demonstrated path |
| Offline protocol/model evidence | Invariants, canonical bytes, rejection semantics, concurrency/model properties within published assumptions | A deployed program, validator/runtime behavior, custody safety, or real-value execution |
| Cross-repository integration evidence | Two independently versioned repositories agree on frozen contracts and fixture boundaries | Production interoperability beyond those exact contracts |

## External Execution proof ledger

| Milestone | Environment | Demonstrated result | Evidence |
|---|---|---|---|
| SA-GW-002 | Solana devnet | real SPL message preparation, local policy, simulation, exact message hash, durable replay | [public Solana-Agent proof](https://github.com/4LFR3Dv1/Solana-Agent/blob/main/docs/evidence/sa-gw-002-live-devnet.md) |
| FP-AUTH-001 | deterministic | Foundry recalculates the commitment and emits a short-lived, single-use authorization bound to exact message bytes | [`FP-AUTH-001.md`](../evidence/runs/FP-AUTH-001.md) |
| FP-SIGN-001 | deterministic | signer validates the authorization and signs only the authorized serialized message | [`FP-SIGN-001.md`](../evidence/runs/FP-SIGN-001.md) |
| SA-EXEC-001 | deterministic RPC | signature-first persistence, one controlled-runtime broadcast, consultable status and recovery | [public Solana-Agent proof](https://github.com/4LFR3Dv1/Solana-Agent/blob/main/docs/evidence/sa-exec-001.md) |
| FP-E2E-001 | Solana devnet | governed SPL transfer finalized; `1,000,000` base units reconciled; one gateway broadcast | [`README`](../evidence/runs/FP-E2E-001/README.md), [`live-proof.json`](../evidence/runs/FP-E2E-001/live-proof.json) |
| FP-REC-001 | two live devnet RPC providers | L1 and L2 observations matched; consensus approved | [`README`](../evidence/runs/FP-REC-001/README.md), [`manifest.json`](../evidence/runs/FP-REC-001/manifest.json) |
| FP-FAIL-001 | deterministic in-process | modeled failure states fail closed, preserve recovery state, and do not authorize blind retry | [`README`](../evidence/runs/FP-FAIL-001/README.md), [`manifest.json`](../evidence/runs/FP-FAIL-001/manifest.json) |
| FP-FAIL-002 | real OS processes with deterministic upstream | eight gateway/proxy scenarios plus reconciliation convergence; every proxy send count is at most one | [`README`](../evidence/runs/FP-FAIL-002/README.md), [`master-demo.json`](../evidence/runs/FP-FAIL-002/master-demo.json), [`journal-root.json`](../evidence/runs/FP-FAIL-002/journal-root.json) |

## Canonical live devnet proof

The governed transfer is publicly observable on
[Solana Explorer](https://explorer.solana.com/tx/RzgQYATtgFZNG7eDgktPAaKh3R922BEjYNLRnvM7u96eFjsnSe4aFYQAtgaP4Hi7kyn91itF1eTEeo498NJ8uS4?cluster=devnet).

```text
network                  solana:devnet
slot                     478403722
amount_base_units        1000000
source delta            -1000000
destination delta       +1000000
prepared_message_hash    sha256:1aac4e92ecb84e91ac69d34d5f1f7040ff6ffde2988477e6b7eff6d5fc341d9b
execution_commitment     sha256:1b79470062864179b011b5803843389f574d998d30e7afbf3a9fcb3962cbf8ff
```

The transaction was finalized and the balance changes matched the approved
obligation. The evidence supports this exact demonstrated path; it does not
establish mainnet or production readiness.

## Source-diverse reconciliation

FP-REC-001 queried the same finalized transaction through two operationally
distinct devnet providers and normalized each observation independently.

```text
L1 observation  sha256:20147b7ceb7fa8190a9f354c6d7d36707e716ba20d8aace3eb3f8508817a2cf4
L2 observation  sha256:e465874ba90be369df1616edd226a083a0aaa5797001e4d4595f753971ac4121
consensus       approved
```

No credential-bearing endpoint is stored in the repository. L2 establishes
provider diversity for this observation; it is not an L3 or institutionally
independent attestation.

## Canonical recovery demonstration

FP-FAIL-002 runs the gateway, fault proxy, and upstream as separate processes.
Its canonical scenario is:

```text
upstream accepts transaction
→ proxy persists upstream response
→ proxy drops client response
→ gateway records needs_recovery
→ gateway restarts
→ recover queries the persisted signature
→ recovered_confirmed
```

Observed invariants:

```text
sendTransaction requests received = 1
upstream requests forwarded       = 1
client responses delivered        = 0
rebroadcasts                      = 0
```

The committed process evidence is bound by:

```text
artifact_root  sha256:483b8a6fd7a73a65f086c5f5b9fd4d7758f581243b1926b6d5c0288093de8899
journal_root   sha256:a48b2303b908a928e1901a099bec67c45a7e1302cb67fe158159d7ef08056070
```

GitHub Actions run
[`30049637775`](https://github.com/4LFR3Dv1/Foundry-Pay/actions/runs/30049637775)
published the journal checkpoint outside the local runtime domain. The
committed repository evidence is the primary public record; GitHub Actions
artifact downloads are supplementary and may require GitHub authentication.

## Foundry Channels evidence summary

The Channels evidence is intentionally separated from live-chain claims. The
following groups are integrated evidence, not production deployment claims.

| Evidence group | Integrated work | Demonstrated boundary |
|---|---|---|
| Protocol runtime | `FC-PROTO-001` through `FC-PROTO-007` | accounting/funding, cumulative vouchers, dual-signature recipient binding, settlement/recovery, close/refund, normative canonicalization, and Python/TypeScript/Rust conformance |
| Security | `FC-SEC-002`, `FC-SEC-003`, `FC-SEC-004` | replay/collision/downgrade rejection, claim-link secret handling, and offline concurrency/linearizability evidence |
| Solana program models | `FC-SOL-002`, `FC-SOL-003`, `FC-SOL-003A`, `FC-SOL-004`, `FC-SOL-005` | fixed-width account/PDA model, instruction and Ed25519 contracts, transition invariants, concurrency preconditions, governance and rights-preserving migration policy |
| Solana-Agent integration | `SA-CHAN-000`, `SA-CHAN-001`, `SA-CHAN-001A`, `SA-CHAN-001B` | fake capability adapter, pinned ChannelVault discovery, durable operation commitments, and fixture-only preparation contracts |

Selected reproducible model depth includes:

- `FC-PROTO-007`: independent Python, TypeScript, and Rust runners over frozen
  positive and negative canonicalization vectors;
- `FC-SOL-004`: 1,536 generated property cases, 703 explored states, 4,732
  attempted transitions, and zero invariant violations within the published
  model and bounds;
- `FC-SEC-004`: 14 bounded commit schedules with 14 explicit serial witnesses
  plus 512 property cases within the versioned-snapshot model.

These results do not prove Solana runtime account locking, CPI rollback,
validator scheduling, a deployed loader/program, formal verification, external
security review, or real-value safety.

Only a future authoritative ChannelVault observation may establish an
`activated` channel right. The offline reference runtime may record states such
as `issued`, `verified`, and `activation_requested`; it cannot manufacture an
on-chain right.

For exact commits, hashes, CI identifiers, and per-work-item evidence paths,
read [`docs/channels/EVIDENCE_INDEX.md`](channels/EVIDENCE_INDEX.md).

## How to verify the public evidence

A reviewer can start without a wallet, RPC endpoint, Solana CLI, or funds:

```text
git clone https://github.com/4LFR3Dv1/Foundry-Pay.git
cd Foundry-Pay
python -m venv .venv
python -m pip install -e ".[dev]"
python examples/local_proof.py
python -m pytest
npm ci --prefix packages/external-execution-protocol/typescript
npm test --prefix packages/external-execution-protocol/typescript
npm ci --prefix packages/channel-protocol/typescript
npm test --prefix packages/channel-protocol/typescript
```

The live transaction can then be checked independently through the Solana
Explorer link above. The committed evidence directories contain manifests,
fixtures, hashes, and explicit limitations for the individual claims.

External reproduction is valuable evidence. A useful contribution is to run
these paths in a clean environment and open an issue containing the exact
environment, commands, and result. Do not publish secrets, seed phrases,
private keys, or credential-bearing RPC URLs.

## Public disclosure boundary

`4LFR3Dv1/Foundry-Pay` is a public Apache-2.0 reference repository. Its public
source, deterministic reference implementations, protocol contracts, tests,
documentation, and sanitized evidence are intended to be inspectable and
reproducible.

The independent `4LFR3Dv1/Solana-Agent` repository is also public and preserves
executor-side evidence without importing the Foundry Pay economic-authority
kernel.

Public evidence deliberately excludes:

- private or ephemeral signing material;
- authorization secrets;
- credential-bearing RPC endpoints;
- raw signed transaction bytes from chaos fixtures where disclosure is not
  required for the claim;
- customer or production data;
- production custody, proprietary connector, and private risk-rule material.

Sanitization is not permission to broaden claims. Missing private material must
not be inferred to exist, be production-ready, or have been independently
audited.

## Claims not made

The current evidence does not claim:

- exactly-once blockchain execution;
- arbitrary-failure tolerance;
- production or mainnet readiness;
- a deployed ChannelVault program;
- live channel funding, activation, claim, settlement, close, or refund;
- production HSM/MPC or custody safety;
- externally audited security;
- L3 independent verification;
- universal economic idempotency for arbitrary token transfers;
- a deployed consumer product, proven product demand, or independent adoption;
- that self-validation or a merged work item is equivalent to external review
  or deployment authorization.

The defensible External Execution property is:

> At-most-one broadcast by the controlled runtime, with signature-first
> recovery and no automatic rematerialization while the economic outcome is
> unknown.

The defensible Foundry Channels property is narrower:

> The published offline protocol, conformance, security, and Solana program
> models satisfy their committed invariants and rejection semantics within the
> exact documented assumptions, fixtures, and bounds. They do not declare
> on-chain rights or deployment readiness.
