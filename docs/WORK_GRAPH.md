# Work Graph

This file is the execution-authority surface for top-level Foundry Pay work.
It answers one question:

> What work is integrated, blocked, ready to be activated, or actively owned?

It does **not** define strategic priority or prove maturity:

- [`ROADMAP.md`](../ROADMAP.md) defines strategic direction;
- [`docs/EVIDENCE.md`](EVIDENCE.md) defines demonstrated claims and evidence maturity;
- this file defines top-level execution readiness and delegation;
- [`docs/channels/WORK_GRAPH.md`](channels/WORK_GRAPH.md) is the delegated execution authority for Foundry Channels (`FC-*` and `SA-CHAN-*`).

Status values are `blocked`, `ready`, `active`, `review`, and `done`.

`done` means the work item was delivered and integrated. It does not mean
externally audited, deployment-authorized, mainnet-ready, or production-ready.
Where maturity or environment authorization matters, the evidence record and
the applicable governance decision remain authoritative.

## Top-level control and documentation

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FP-CTRL-001 | done | - | initial repository control baseline |
| FP-CTRL-002 | done | FP-CTRL-001 | `AGENTS.md` operating agreement |
| FP-CTRL-003 | done | FP-CTRL-001 | task and review contracts |
| FP-CTRL-004 | done | FP-CTRL-001 | CI and secret scanning |
| FP-CTRL-005 | active | FP-CTRL-001 | maintain top-level work graph, decision ledger, and authority delegation |
| FP-ADR-001 | done | FP-CTRL-001 | external-first execution decision |
| FP-DOC-001 | done | FP-E2E-001, FP-REC-001, FP-FAIL-002 | current-state README and evidence index |
| FP-DOC-002 | done | FP-DOC-001, FP-FAIL-002 | public repository visibility and honest review metadata |
| FP-DOC-003 | done | FP-DOC-002 | Apache-2.0 boundary and external onboarding |
| FP-DOC-004 | done | FP-DOC-003, FC-CTRL-013 | public onboarding synchronized with implemented Channels protocol |
| FOUNDATIONS-001 | done | FP-DOC-003 | Foundry Channels architecture foundation integrated; successor authority delegated to the Channels graph |

Repository visibility is public. Completion of `FOUNDATIONS-001` does not
authorize an operational ChannelVault or any deployment environment.

## External Execution track

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FP-PROTO-001 | done | FP-ADR-001 | v1 protocol schemas |
| FP-PROTO-002 | done | FP-PROTO-001 | normalization and normative hashes |
| FP-PROTO-003 | done | FP-PROTO-001, FP-PROTO-002 | fake executor and conformance kit |
| FP-PROTO-004 | ready | FP-PROTO-001 | stabilize errors, capabilities, and version negotiation |
| FP-PROTO-005 | ready | FP-PROTO-001 | correlated journal and evidence-manifest contracts |
| FP-PROTO-006 | ready | FP-PROTO-001 | simulation validity and drift handling |
| FP-PROTO-007 | done | FP-PROTO-003, SA-GW-002 | bind `obligation_id` in the v1 execution commitment |
| SA-BASE-001 | done | FP-ADR-001 | immutable Solana-Agent baseline |
| SA-GW-001 | done | FP-PROTO-003, SA-BASE-001 | JSONL gateway |
| SA-GW-002 | done | SA-GW-001 | live devnet SPL preparation and simulation |
| FP-AUTH-001 | done | FP-PROTO-007, SA-GW-002 | short-lived exact-message execution authorization |
| FP-SIGN-001 | done | FP-AUTH-001 | exact-message signer boundary |
| SA-EXEC-001 | done | FP-SIGN-001, SA-GW-002 | single broadcast, status, recovery, and technical evidence |
| FP-E2E-001 | done | FP-SIGN-001, SA-EXEC-001 | governed Solana devnet remediation proof |
| FP-REC-001 | done | FP-E2E-001 | source-diverse reconciliation and consensus |
| FP-FAIL-001 | done | FP-E2E-001, FP-REC-001 | deterministic failure and recovery matrix |
| FP-FAIL-002 | done | FP-FAIL-001, SA-CHAOS-001 | real-process chaos proxy, recovery, and external journal root |

`FP-FAIL-002` is delivered. Its independent external security review remains
`not_performed`; that maturity fact is recorded separately from work-item
completion and must not be inferred from `done`.

## External verification

| Work item | Status | Depends on | Outcome |
|---|---|---|---|
| FP-VER-001 | ready | FP-DOC-004, FP-FAIL-002, FOUNDATIONS-001 | independent developer reproduces and challenges the pinned public baseline, or publishes a valid non-reproduction finding |

`FP-VER-001` is the formal execution authority for the Roadmap's first external
developer verification. Its normative contract is
[`docs/EXTERNAL_VERIFICATION.md`](EXTERNAL_VERIFICATION.md), with the activation
contract in [`.agents/tasks/FP-VER-001.yaml`](../.agents/tasks/FP-VER-001.yaml).

`ready` does not mean an external verification has occurred. Activation requires
an independent verifier, an immutable baseline commit, and a pre-recorded scope.
The verifier must operate the clean environment. A maintainer may coordinate the
run but cannot author the verifier's result and present it as independent.

A valid run may conclude `reproduced`, `reproduced_with_findings`, or
`not_reproduced`; `invalid_run` is reserved for a run whose independence,
baseline, or evidence contract is invalid. An unfavorable reproducible result
must remain visible.

This work item creates **external developer verification** authority only. It
does not create a professional security-audit gate, deployment authorization,
mainnet authority, real-value authority, custody authority, or production
readiness.

## Delegated Foundry Channels authority

Foundry Channels no longer mirrors its detailed state into this top-level table.
The canonical sources are:

- [`docs/channels/WORK_GRAPH.md`](channels/WORK_GRAPH.md) for human-readable execution state;
- [`docs/channels/work-items.yaml`](channels/work-items.yaml) for the executable work-item registry;
- [`docs/channels/EVIDENCE_INDEX.md`](channels/EVIDENCE_INDEX.md) for Channels evidence and maturity;
- [`docs/channels/ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md`](channels/ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md) for the separation between delivery, review, and deployment authorization.

At the current delegated boundary, `SA-CHAN-002`, `SA-CHAN-003`, and
`FC-FAIL-003` are ready in the Channels graph. Later ChannelVault handlers,
signer/RPC execution, deployment environments, mainnet, and real-value use
remain blocked unless a later work item and explicit authorization release them.

`FC-VAL-003` requires special care: its public research protocol exists, but
human recruitment is not authorized until the private research-storage,
consent, privacy-review, and immutable-run-manifest gates documented in
[`docs/channels/validation/FC-VAL-003/README.md`](channels/validation/FC-VAL-003/README.md)
are satisfied. A strategic priority in the Roadmap is not itself recruitment
authority.

## Historical product-discovery sketch

The original `FP-PROD-001` through `FP-PROD-003` operator-discovery sketch is
not current execution authority. Product validation for Foundry Channels is now
governed by the delegated `FC-VAL-*` and `FC-PROD-*` graph. Reviving the older
`FP-PROD-*` lane requires an explicit new decision and bounded work item; it
must not be inferred as `ready` from historical documents.

## Active ownership and path reservation

Only `active` work owns paths. A `ready` item is eligible to receive a bounded
task contract; readiness alone does not reserve files.

| Work item | Current ownership |
|---|---|
| FP-CTRL-005 | top-level operational governance: `AGENTS.md`, `docs/WORK_GRAPH.md`, `docs/PROGRAM.md`, `docs/DECISIONS.md`, contribution/governance documentation, and authority-delegation references |

Before activating `FP-PROTO-004`, `FP-PROTO-005`, `FP-PROTO-006`, or
`FP-VER-001`, bind the exact baseline and paths required by that run and verify
that no active or delegated work owns them.

For `FP-VER-001`, the verification target itself is read-only. Optional imported
reports may use `evidence/external/FP-VER-001/**`; `docs/EVIDENCE.md` may be
updated only after a valid original verifier-authored record exists.

Channels path ownership is defined only in its delegated work-item contracts.

## Completed first proof gate

The original External Execution gate is complete. The repository has
demonstrated:

1. normative cross-language hashing;
2. rejection of mutated, expired, or replayed authorization;
3. exact-message authorization and signer isolation;
4. a governed SPL transfer on Solana devnet;
5. source-diverse reconciliation;
6. recovery from ambiguous and lost-response outcomes without blind retry;
7. deterministic and real-process failure evidence.

See [`docs/EVIDENCE.md`](EVIDENCE.md) for the exact proof boundary and remaining
non-claims.

## Authorization rule

Neither a Roadmap entry nor an Evidence claim releases work by itself.

```text
Roadmap priority
!= work-item readiness
!= active path ownership
!= evidence maturity
!= external review
!= deployment authorization
```

A new capability starts only after the governing work graph and task contract
make that authority explicit.
