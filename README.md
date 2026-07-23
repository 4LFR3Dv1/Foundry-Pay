# Foundry Pay

Governed reconciliation and controlled remediation for stablecoin operations.

Foundry Pay is the economic authority and final verifier. Specialized external
executors prepare, simulate, execute, confirm, and recover network-specific
operations under explicit, limited authorization.

## Current state

The first governed Solana proof is complete:

```text
economic plan
→ exact Solana message
→ short-lived single-use authorization
→ isolated signature
→ one broadcast
→ finalized devnet transaction
→ L1/L2 reconciliation
→ hash-bound evidence
```

One approved SPL transfer moved `1,000,000` base units on Solana devnet. The
authorization was bound to the exact serialized message, the resulting balance
deltas matched the obligation, and two distinct RPC providers observed the
finalized transaction. A separate nine-scenario process matrix demonstrated
signature-first recovery and no second controlled-runtime broadcast under the
modeled failures.

This is proof-of-work, not a production-readiness claim. Mainnet operations,
L3 observation, external security review, sustained operation, and
production-grade signer infrastructure remain open gates.

## Architecture

```text
Foundry Pay                   Solana-Agent                 Signer
economic authority           network specialist          exact-byte boundary
global policy                local policy                 no business authority
approval + authorization  →  prepare/simulate/execute  →  sign only commitment
reconciliation               status/recover/evidence
```

Foundry never sends free-form prompts across the execution boundary. The two
systems exchange versioned protocol objects and correlate them by
`execution_request_id`, `obligation_id`, `plan_hash`, and
`execution_commitment_hash`.

## Evidence

The [evidence index](docs/EVIDENCE.md) separates:

- live devnet preparation and execution;
- exact-message authorization and signer checks;
- L1/L2 reconciliation;
- deterministic failure and real-process chaos matrices;
- residual claims that have not yet been demonstrated.

A sanitized public system snapshot is maintained in the
[Solana-Agent public repository](https://github.com/4LFR3Dv1/Solana-Agent/tree/main/docs/evidence).

## Verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
```

## Start here

1. Read `AGENTS.md`.
2. Read `docs/ADR/FP-ADR-001-external-first.md`.
3. Review `docs/EVIDENCE.md`.
4. Select a ready item from `docs/WORK_GRAPH.md`.
5. Create a task contract from `.agents/task-template.yaml`.

This repository publishes the reference protocol, sanitized proof-of-work, and
reproducible evidence. Production credentials, customer data, custody
infrastructure, and deployment configuration are not included. Solana-Agent
remains an independent Apache-2.0 public good and integrates only through the
`ExternalExecutionAgent` protocol.
