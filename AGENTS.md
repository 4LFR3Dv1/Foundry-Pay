# Foundry Pay Agent Operating Agreement

This file is the operational constitution for every human or software agent
working in this repository. Read it before changing files.

## Mission

Build governed payment infrastructure for stablecoin systems and agentic
applications without collapsing economic authority into network execution.

Foundry Pay has already demonstrated the first External Execution proof on
Solana devnet: exact-message authorization, isolated signing, one controlled
broadcast, source-diverse reconciliation, recovery, and reproducible evidence.
The current program extends that baseline through protocol stabilization,
external verification, Foundry Channels, and only later explicitly authorized
execution environments.

## Authority surfaces

The repository deliberately separates different kinds of authority:

- `README.md` explains what the project is and how to evaluate it;
- `ROADMAP.md` defines strategic direction and desired future capabilities;
- `docs/EVIDENCE.md` defines what has actually been demonstrated and at what maturity;
- `docs/WORK_GRAPH.md` is execution authority for top-level `FP-*` work and shared control;
- `docs/channels/WORK_GRAPH.md` plus `docs/channels/work-items.yaml` are delegated execution authority for Foundry Channels (`FC-*` and `SA-CHAN-*`);
- ADRs and decision ledgers own architectural decisions;
- task contracts own exact acceptance criteria and allowed paths for active work.

No lower-authority surface may silently override a higher-specificity decision.
In particular:

```text
Roadmap priority
!= work-item readiness
!= active path ownership
!= demonstrated evidence
!= external review
!= deployment authorization
```

## Architectural authority

- Foundry Pay owns economic intent, global policy, economic approval, execution
  authorization, reconciliation, and the final business result.
- External executors own only local safety, preparation, simulation,
  transmission, technical confirmation, recovery, and technical receipts.
- A signer signs only the exact prepared message covered by a valid,
  short-lived, single-use `ExecutionAuthorization`.
- No local policy may broaden a global permission.
- Solana-Agent is an independent external executor. Do not import or extract
  its kernel.
- The execution protocol is transport-independent. JSONL over stdin/stdout is
  the first adapter, not part of the domain authority model.

The governing External Execution decision is
`docs/ADR/FP-ADR-001-external-first.md`.

Foundry Channels adds its own public protocol and authority model without
changing this split. Channel-specific decisions are governed under
`docs/channels/`.

## Non-negotiable invariants

1. Free-form prompts never cross an execution boundary.
2. Signed objects use their versioned normalization and canonicalization rules.
3. `prepared_message_hash` is SHA-256 of the exact serialized transaction
   message bytes.
4. Any changed message byte requires a new preparation, simulation, commitment,
   and authorization.
5. An unknown broadcast outcome becomes `needs_recovery`; it is never retried
   automatically.
6. No new message is materialized while the outcome of the previous message for
   the same obligation is unknown.
7. Executor receipts are evidence inputs, not declarations of business success.
8. Claims of source-diverse reconciliation identify the actual independent
   observation boundary.
9. Secrets, private keys, seed phrases, tokens, participant PII, and production
   customer data never enter the public repository or public evidence bundles.
10. Evidence is produced from execution, tests, or controlled observation; it
    is not fabricated by hand.
11. Work-item completion never implies external review or deployment authority.
12. Mainnet or real-value execution requires the exact review and explicit
    authorization demanded by the applicable governance policy.

## Required workflow

Every material change starts from the graph that owns its namespace:

- top-level `FP-*` and shared control: `docs/WORK_GRAPH.md`;
- Foundry Channels `FC-*` and `SA-CHAN-*`: `docs/channels/WORK_GRAPH.md` and
  `docs/channels/work-items.yaml`.

Then:

1. Confirm the work item is `ready` or `active` in the governing graph.
2. Confirm dependencies and reconcile a task contract from
   `.agents/task-template.yaml` or the program-specific contract.
3. Reserve exact `allowed_paths`; `ready` status alone does not reserve files.
4. Work on a branch named `agent/<area>/<work-item>` unless the bounded task is
   an explicitly authorized documentation/control reconciliation.
5. Make the smallest vertical change satisfying the acceptance criteria.
6. Run relevant tests and capture commands/results in `evidence/runs/` when the
   work item requires generated evidence.
7. Record architectural decisions in the applicable ADR/decision ledger.
8. Update `provenance/REUSE_LEDGER.yaml` before reusing external code.
9. Obtain the review required by the task contract and environment policy.
10. Update the governing work graph only from evidence-backed state.

Independent external review is never inferred from self-validation. Where a
task contract, ADR, or deployment policy requires an independent reviewer, the
author cannot satisfy that gate alone.

## Work-item maturity and deployment authority

For Foundry Channels, `FC-ADR-009` explicitly separates:

```text
work item delivered
self-validation passed
external review passed for an exact version
deployment authorized for an exact artifact/environment
```

A work item may therefore be `done` while external review is `not_performed`
and deployment remains blocked. Preserve those distinctions in every public
claim.

The same principle must be respected by top-level documentation: do not use a
work-graph status as shorthand for audit, mainnet, production, adoption, or
safety claims.

## Scope and path ownership

- `packages/domain/**`: deterministic business types and normalization inputs.
- `packages/external-execution-protocol/**`: schemas, canonicalization,
  commitments, authorization, evidence formats, and conformance tests.
- `packages/external-execution-client/**`: transport clients only.
- `packages/channel-protocol/**` and `contracts/channel/**`: public Foundry
  Channels protocol/model surfaces under the delegated Channels graph.
- `services/**`: Foundry authority and workers; never executor internals.
- `apps/**`: operator-facing interfaces; never forge runtime evidence.
- `fixtures/**`: synthetic or sanitized data only.
- `evidence/**`: generated artifacts, manifests, and test reports.
- `provenance/**`: immutable source SHAs, ownership, licenses, and reuse records.
- `submissions/**`: narrative projections; no business logic.

Changes outside an active task's `allowed_paths` are a stop condition.
Cross-program path conflicts stop work until the owning graph is reconciled.

## Research boundary

Product validation is not an exception to repository authority or privacy
rules. In particular, the public `FC-VAL-003` protocol does not authorize human
recruitment by itself. Its private storage, consent, privacy-review, and
immutable-run-manifest gates must be satisfied before participant work begins.
No raw participant record belongs in this repository.

## Reuse policy

- Pin the source repository and immutable commit.
- Record source paths, destination paths, ownership, license, modifications, and
  verification.
- Repositories without an explicit compatible license are reference-only until
  ownership and licensing are documented.
- Preserve attribution and notices.
- Characterize behavior before refactoring or adapting it.
- Never remove authorship history or copy code through generated output to evade
  provenance.

## Verification gates

Minimum PR gate:

- relevant schema and unit tests pass;
- cross-language vectors pass when multiple implementations exist;
- negative and tamper cases pass where applicable;
- secrets scan passes;
- provenance is complete;
- evidence references the exact commit and command when evidence is required;
- docs and governing work graph reflect the implementation;
- no claim exceeds the evidence or environment authorization.

Security-, protocol-, signer-, and money-moving changes may impose stronger
gates in their task contracts or ADRs. Those stronger gates win.

## Stop and escalate

Stop work and report the condition when:

- a contract change breaks compatibility without a version decision;
- a secret, participant PII, or non-sanitized customer artifact is found;
- broadcast state is ambiguous;
- a requested action would broaden executor authority;
- reuse ownership or license is unresolved;
- a task requires paths owned by another active work item;
- a Roadmap priority is being treated as execution authorization;
- a work-item status is being treated as external review or deployment authority;
- research recruitment is attempted without its private/privacy gates;
- evidence cannot be reproduced.

## Canonical references

- `README.md`
- `ROADMAP.md`
- `docs/EVIDENCE.md`
- `docs/PROGRAM.md`
- `docs/WORK_GRAPH.md`
- `docs/DECISIONS.md`
- `docs/ARCHITECTURE.md`
- `docs/EXTERNAL_EXECUTION_PROTOCOL.md`
- `docs/ADR/FP-ADR-001-external-first.md`
- `docs/channels/PROGRAM.md`
- `docs/channels/WORK_GRAPH.md`
- `docs/channels/work-items.yaml`
- `docs/channels/EVIDENCE_INDEX.md`
- `docs/channels/ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md`
- `provenance/REUSE_LEDGER.yaml`
