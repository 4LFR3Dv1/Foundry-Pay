# Foundry Pay

Governed reconciliation and controlled remediation for stablecoin operations.

Foundry Pay is the economic authority and final verifier. Specialized external
executors prepare, simulate, execute, confirm, and recover network-specific
operations under explicit, limited authorization.

## Current milestone

Prove one synthetic divergence correction on Solana devnet through the external
Solana-Agent:

- no duplicated economic effect;
- authorization bound to exact serialized message bytes;
- consultable recovery after a lost response;
- L2 reconciliation;
- verifiable evidence bundle.

## Start here

1. Read `AGENTS.md`.
2. Read `docs/ADR/FP-ADR-001-external-first.md`.
3. Select a ready item from `docs/WORK_GRAPH.md`.
4. Create a task contract from `.agents/task-template.yaml`.

This repository is private product infrastructure. Solana-Agent remains an
independent Apache-2.0 public good and integrates only through the
`ExternalExecutionAgent` protocol.
