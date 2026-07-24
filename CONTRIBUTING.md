# Contributing to Foundry Pay

Foundry Pay welcomes focused contributions to the public protocol, reference
implementations, tests, sanitized fixtures, documentation, and developer
tooling.

## Before you start

1. Read `README.md`, `AGENTS.md`, and
   `docs/ADR/FP-ADR-001-external-first.md`.
2. Check `docs/WORK_GRAPH.md` for dependencies and active path reservations.
3. Open an issue for material protocol, authority, or compatibility changes.
4. Create a task contract from `.agents/task-template.yaml`.
5. Work on a branch named `agent/<area>/<work-item>`.

Small documentation and test fixes may use a compact work item, but they must
still respect ownership, provenance, secret-handling, and path reservations.

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

## Required checks

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
npm test --prefix packages/external-execution-protocol/typescript
git diff --check
```

Run narrower tests while developing, then run the complete relevant gate before
requesting review.

## Pull requests

A pull request should:

- identify its work item and smallest verifiable outcome;
- explain whether authority or protocol compatibility changes;
- include positive, negative, tamper, and recovery coverage where relevant;
- record verification commands and generated evidence;
- update documentation, decisions, work graph, and provenance as needed;
- contain no secrets, wallet material, production data, or customer artifacts.

An author cannot be the only approver of a security- or money-moving change.

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
- deterministic reference implementations and adapters;
- tests, failure injection, recovery, and evidence verification;
- sanitized examples, documentation, and developer experience.

Do not submit production credentials, customer data, custody infrastructure,
deployment secrets, private risk rules, or proprietary connectors without
explicit authorization from their owner.

See `docs/PUBLIC_COMMERCIAL_BOUNDARY.md`.
