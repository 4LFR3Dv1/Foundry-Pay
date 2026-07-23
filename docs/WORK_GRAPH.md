# Work Graph

Status values: `blocked`, `ready`, `active`, `review`, `done`.

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FP-CTRL-001 | active | - | canonical private repository |
| FP-CTRL-002 | done | FP-CTRL-001 | `AGENTS.md` |
| FP-CTRL-003 | done | FP-CTRL-001 | task and review contracts |
| FP-CTRL-004 | done | FP-CTRL-001 | CI and secret scanning |
| FP-CTRL-005 | active | FP-CTRL-001 | work graph and decision ledger |
| FP-ADR-001 | done | FP-CTRL-001 | external-first decision |
| FP-PROTO-001 | done | FP-ADR-001 | v1 protocol schemas |
| FP-PROTO-002 | done | FP-PROTO-001 | normalization and three hashes |
| FP-PROTO-003 | done | FP-PROTO-001, FP-PROTO-002 | fake executor and conformance kit |
| FP-PROTO-004 | ready | FP-PROTO-001 | errors, capabilities, versioning |
| FP-PROTO-005 | ready | FP-PROTO-001 | correlated journal and evidence manifest |
| FP-PROTO-006 | ready | FP-PROTO-001 | simulation validity and drift |
| FP-PROTO-007 | done | FP-PROTO-003, SA-GW-002 | bind `obligation_id` in the draft v1 commitment |
| SA-BASE-001 | done | FP-ADR-001 | immutable Solana-Agent baseline |
| SA-GW-001 | done | FP-PROTO-003, SA-BASE-001 | JSONL gateway |
| SA-GW-002 | done | SA-GW-001 | live devnet SPL preparation and simulation |
| FP-AUTH-001 | done | FP-PROTO-007, SA-GW-002 | short-lived exact-message execution authorization |
| FP-SIGN-001 | review | FP-AUTH-001 | validate authorization and sign only exact prepared bytes |
| FP-PROD-001 | ready | - | three operator interviews |
| FP-PROD-002 | blocked | FP-PROD-001 | five frequent incidents |
| FP-PROD-003 | blocked | FP-PROD-002 | sanitized incident fixture |

## Active path reservations

| Work item | Allowed paths |
|---|---|
| FP-CTRL-001/005 | repository root, `.agents/**`, `docs/**`, `provenance/**` |
| FP-PROTO-001/002 | `packages/external-execution-protocol/**`, `tests/protocol/**` |
| FP-PROTO-007 | protocol package, protocol tests, protocol docs, task contract, evidence |
| FP-AUTH-001 | authorization service, authorization tests, protocol docs, task/review contracts, evidence |
| FP-SIGN-001 | signer service, signer tests, protocol docs, task/review contracts, evidence |

## First gate

Foundry and a fake executor:

1. calculate identical hashes from normative vectors;
2. reject mutated, expired, or replayed authorization;
3. recover a simulated response loss;
4. do not duplicate the economic effect.
