# Foundry Pay evidence index

This index is the claim boundary for the current Foundry Pay proof. Every
completed claim below points to committed evidence. Live-chain observations
are kept separate from deterministic and emulated failure tests.

## Proof ledger

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

## Live devnet settlement

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
obligation.

## Source-diverse reconciliation

FP-REC-001 queried the same finalized transaction through two operationally
distinct devnet providers and normalized each observation independently.

```text
L1 observation  sha256:20147b7ceb7fa8190a9f354c6d7d36707e716ba20d8aace3eb3f8508817a2cf4
L2 observation  sha256:e465874ba90be369df1616edd226a083a0aaa5797001e4d4595f753971ac4121
consensus       approved
```

No credential-bearing endpoint is stored in the repository. L2 proves provider
diversity; it is not an L3 or institutionally independent attestation.

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
published the journal checkpoint outside the local runtime domain. The Foundry
repository and its Actions artifacts currently require repository access.

## Public disclosure boundary

The public Solana-Agent repository contains a sanitized, machine-readable
system snapshot and its executor-side proofs. Foundry retains the complete
authorization, reconciliation, and scenario artifacts in this private
repository. Public evidence excludes:

- private or ephemeral signing material;
- authorization secrets;
- credential-bearing RPC endpoints;
- raw signed transaction bytes from chaos fixtures;
- customer or production data.

## Claims not made

The current evidence does not claim:

- exactly-once blockchain execution;
- arbitrary-failure tolerance;
- production or mainnet readiness;
- L3 independent verification;
- HSM/MPC production custody;
- externally audited security;
- universal economic idempotency for arbitrary SPL transfers.

The defensible property is:

> At-most-one broadcast by the controlled runtime, with signature-first
> recovery and no automatic rematerialization while the economic outcome is
> unknown.
