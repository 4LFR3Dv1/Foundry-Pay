# Decision Ledger

This ledger records top-level Foundry Pay decisions and delegates
Foundry-Channels-specific decisions to `docs/channels/DECISIONS.md` and its
ADRs.

| Decision | Status | Record |
|---|---|---|
| External-first, protocol-first execution | accepted | `ADR/FP-ADR-001-external-first.md` |
| Two-phase PREPARE/COMMIT flow | accepted | `ADR/FP-ADR-001-external-first.md` |
| Exact serialized message bytes are authorized | accepted | `ADR/FP-ADR-001-external-first.md` |
| Unknown broadcast forbids automatic retry | accepted | `ADR/FP-ADR-001-external-first.md` |
| Financial values are decimal base-unit strings | accepted | `EXTERNAL_EXECUTION_PROTOCOL.md` |
| First External Execution proof uses `solana:devnet` and `solana.spl_transfer.v1` | accepted and demonstrated | `EXTERNAL_EXECUTION_PROTOCOL.md`, `EVIDENCE.md` |
| Signed protocol objects reject null, floats, unsafe integers, and lone surrogates where the profile requires it | accepted | `EXTERNAL_EXECUTION_PROTOCOL.md` |
| Unicode is hashed exactly and never normalized silently in the External Execution profile | accepted | `EXTERNAL_EXECUTION_PROTOCOL.md` |
| v1 execution commitments bind `obligation_id` | accepted and integrated | `FP-PROTO-007`, `EXTERNAL_EXECUTION_PROTOCOL.md` |
| JSONL stdio is the first External Execution transport adapter, not domain authority | accepted and integrated | `ADR/FP-ADR-001-external-first.md`, `SA-GW-001` |
| Solana-Agent remains an independent executor rather than an imported Foundry kernel | accepted | `ADR/FP-ADR-001-external-first.md` |
| The public reference implementation is Apache-2.0 with an explicit public/commercial boundary | accepted | `ADR/FP-ADR-002-open-source-boundary.md`, `PUBLIC_COMMERCIAL_BOUNDARY.md` |
| Foundry Channels owns its detailed protocol, execution graph, and decision ledger under `docs/channels/` | accepted delegation | `channels/WORK_GRAPH.md`, `channels/DECISIONS.md` |
| Foundry Channels work completion, self-validation, external review, and deployment authorization are independent facts | accepted | `channels/ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md` |
| Roadmap direction, execution readiness, demonstrated evidence, external review, and deployment authorization are distinct surfaces | accepted operational boundary | `../ROADMAP.md`, `WORK_GRAPH.md`, `EVIDENCE.md`, `AGENTS.md` |

## Delegated Foundry Channels decisions

Do not copy the complete Channels decision set into this ledger. The canonical
records are:

- `channels/DECISIONS.md`;
- `channels/ADR/**`;
- `channels/WORK_GRAPH.md` for execution state;
- `channels/EVIDENCE_INDEX.md` for demonstrated/maturity state.

A top-level decision may constrain Channels, but a top-level summary must not
silently rewrite a more specific accepted Channels ADR.

## Current non-decisions

The following are strategic possibilities or future gates, not accepted
execution/deployment decisions:

- an operational ChannelVault implementation;
- any ChannelVault deployment environment;
- mainnet or real-value Foundry Channels execution;
- a second EVM executor/network;
- Celo as an active execution environment;
- production custody/signing architecture;
- a production service or SLA.

Those require explicit future decisions and the evidence/review gates applicable
to the exact artifacts and environment.
