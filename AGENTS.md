# Foundry Pay Agent Operating Agreement

This file is the operational constitution for every human or software agent
working in this repository. Read it before changing files.

## Mission

Build governed reconciliation and controlled remediation for stablecoin
operations. The first proof is one synthetic divergence corrected on Solana
devnet through the external Solana-Agent without duplicated economic effect,
with authorization bound to exact message bytes, independent reconciliation,
and a verifiable evidence bundle.

## Architectural authority

- Foundry Pay owns economic intent, global policy, economic approval, execution
  authorization, reconciliation, and the final business result.
- External executors own only local safety, preparation, simulation,
  transmission, technical confirmation, recovery, and technical receipts.
- A signer signs only the exact prepared message covered by a valid, short-lived,
  single-use `ExecutionAuthorization`.
- No local policy may broaden a global permission.
- Solana-Agent is an external product. Do not import or extract its kernel.
- The protocol is transport-independent. JSONL over stdin/stdout is the first
  transport, not part of the domain model.

The governing decision is `docs/ADR/FP-ADR-001-external-first.md`.

## Non-negotiable invariants

1. Free-form prompts never cross an execution boundary.
2. Signed objects use the Domain Normalization Profile and normative
   canonicalization.
3. `prepared_message_hash` is SHA-256 of the exact serialized Solana message
   bytes.
4. Any changed message byte requires a new preparation, simulation, commitment,
   and authorization.
5. An unknown broadcast outcome becomes `needs_recovery`; it is never retried
   automatically.
6. No new message is materialized while the outcome of the previous message for
   the same obligation is unknown.
7. Executor receipts are evidence inputs, not declarations of business success.
8. External claims of independent reconciliation require an L2 or L3 source.
9. Secrets, private keys, seed phrases, tokens, and production customer data
   never enter the repository or evidence bundles.
10. Evidence is produced from execution and tests; it is not fabricated by hand.

## Required workflow

Every change starts from a work item in `docs/WORK_GRAPH.md` and a task contract
based on `.agents/task-template.yaml`.

1. Confirm dependencies and reserve `allowed_paths`.
2. Work on a branch named `agent/<area>/<work-item>`.
3. Make the smallest vertical change satisfying acceptance criteria.
4. Run relevant tests and capture commands/results in `evidence/runs/`.
5. Record architectural decisions in `docs/ADR/`.
6. Update `provenance/REUSE_LEDGER.yaml` before reusing external code.
7. Request independent review using `.agents/review-template.yaml`.
8. Update the work graph only from evidence-backed state.

An author cannot be the only approver of a security- or money-moving change.

## Scope and path ownership

- `packages/domain/**`: deterministic business types and normalization inputs.
- `packages/external-execution-protocol/**`: schemas, canonicalization,
  commitments, authorization, evidence formats, and conformance tests.
- `packages/external-execution-client/**`: transport clients only.
- `services/**`: Foundry authority and workers; never executor internals.
- `apps/**`: operator-facing interfaces; never forge runtime evidence.
- `fixtures/**`: synthetic or sanitized data only.
- `evidence/**`: generated artifacts, manifests, and test reports.
- `provenance/**`: immutable source SHAs, ownership, licenses, and reuse records.
- `submissions/**`: narrative projections; no business logic.

Changes outside the task's `allowed_paths` are a stop condition.

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

- schema and unit tests pass;
- cross-language vectors pass when both implementations exist;
- negative and tamper cases pass;
- secrets scan passes;
- provenance is complete;
- evidence references the exact commit and command;
- docs and work graph reflect the implementation.

The first protocol gate additionally requires Foundry and a fake executor to
derive identical hashes, reject mutated/expired authorization, and recover a
simulated lost response without duplicating the effect.

## Stop and escalate

Stop work and report the condition when:

- a contract change breaks backward compatibility without a version decision;
- a secret or non-sanitized customer artifact is found;
- broadcast state is ambiguous;
- a requested action would broaden executor authority;
- reuse ownership or license is unresolved;
- a task requires paths owned by another active work item;
- evidence cannot be reproduced.

## Canonical references

- `docs/PROGRAM.md`
- `docs/ARCHITECTURE.md`
- `docs/EXTERNAL_EXECUTION_PROTOCOL.md`
- `docs/WORK_GRAPH.md`
- `docs/ADR/FP-ADR-001-external-first.md`
- `provenance/REUSE_LEDGER.yaml`
