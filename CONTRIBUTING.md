# Contributing to Foundry Pay

Foundry Pay welcomes focused contributions to the public protocol, reference
implementations, tests, sanitized fixtures, documentation, developer tooling,
and externally reproducible evidence.

## Before you start

1. Read `README.md`, `AGENTS.md`, and the applicable architecture/ADR.
2. Identify the graph that owns the work:
   - top-level `FP-*` and shared control: `docs/WORK_GRAPH.md`;
   - Foundry Channels `FC-*` and `SA-CHAN-*`: `docs/channels/WORK_GRAPH.md` and
     `docs/channels/work-items.yaml`.
3. Confirm the item is allowed to begin. A Roadmap priority is not execution
   authorization, and a `ready` item does not own paths until activated by a
   bounded task contract.
4. Open an issue for material protocol, authority, compatibility, deployment,
   or security changes that are not already covered by an authorized item.
5. Reconcile a task contract from `.agents/task-template.yaml` or the applicable
   program-specific contract and reserve exact paths.
6. Work on a branch named `agent/<area>/<work-item>` unless the governing item
   explicitly defines a different bounded coordination branch.

Small documentation and test fixes may use a compact work item, but they must
still respect authority, provenance, secret handling, privacy, and path
ownership.

## Authority and claim boundaries

Keep these statements separate:

```text
work item delivered
self-validation passed
external review passed
artifact/environment deployment authorized
production ready
```

A merged or `done` work item does not automatically establish any later state.
Do not describe self-validation as independent review or a local/fixture model as
a deployed system.

For Foundry Channels, the normative maturity/deployment policy is
`docs/channels/ADR/FC-ADR-009-evidence-maturity-and-deployment-authorization.md`.

## Local setup

```text
python -m venv .venv

# PowerShell
.venv\Scripts\Activate.ps1

# bash/zsh
source .venv/bin/activate

python -m pip install -e ".[dev]"
npm ci --prefix packages/external-execution-protocol/typescript
```

Channels work may require additional language/package commands defined by its
specific task contract and conformance documentation.

## Required checks

The top-level baseline is:

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
npm test --prefix packages/external-execution-protocol/typescript
git diff --check
```

Run narrower tests while developing, then run the complete gate required by the
governing work item before requesting review. A Channels task may additionally
require the foundation checker, TypeScript/Rust conformance, property tests,
manifest verification, or exact evidence-generation commands.

## Pull requests

A pull request should:

- identify its governing work item and smallest verifiable outcome;
- identify the graph and task contract that authorize its paths;
- explain whether authority, protocol compatibility, maturity, or deployment
  state changes;
- include positive, negative, tamper, recovery, and adversarial coverage where
  relevant;
- record verification commands and generated evidence when the work item
  requires evidence;
- update the governing work graph, decision records, evidence indexes, and
  provenance only when their state actually changes;
- contain no secrets, wallet material, participant PII, production data, or
  customer artifacts;
- state important non-claims when a reader could otherwise infer a stronger
  result than was demonstrated.

Independent external review is not created by calling an internal/self-run
review “independent.” Where a task contract, ADR, or deployment policy requires
an independent reviewer, the author cannot satisfy that gate alone.

## Research contributions

Public research protocols, schemas, and sanitized aggregate formats may live in
this repository when the governing work item allows them. Raw participant data,
consent artifacts, contact information, recordings, transcripts, wallet
activity, or re-identifiable research material must not be committed here.

`FC-VAL-003` is a concrete example: the public protocol exists, but human
recruitment remains prohibited until its private storage, consent,
privacy-review, and immutable-run-manifest gates are actually satisfied.

## Licensing and provenance

Unless explicitly stated otherwise, contributions intentionally submitted for
inclusion are provided under Apache-2.0, as described in `LICENSE`.

Do not submit code, fixtures, media, or documentation unless you have the right
to contribute them. Record reused material in `provenance/REUSE_LEDGER.yaml`,
including its immutable source revision, license, attribution, modifications,
and verification.

Repositories with unresolved licenses are reference-only.

## Public contribution boundary

Appropriate contributions include:

- protocol contracts and conformance vectors;
- deterministic reference implementations and bounded adapters;
- tests, failure injection, recovery, and evidence verification;
- sanitized examples and fixtures;
- documentation and developer experience;
- externally reproducible verification reports that do not expose secrets.

Do not submit production credentials, customer data, custody infrastructure,
deployment secrets, private risk rules, proprietary connectors, or private
research records without explicit authorization from their owner and the
applicable repository boundary.

See `docs/PUBLIC_COMMERCIAL_BOUNDARY.md`.
