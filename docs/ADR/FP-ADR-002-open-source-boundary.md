# FP-ADR-002: Apache-2.0 and the public/commercial boundary

- Status: accepted
- Date: 2026-07-24
- Decision owner: Renan Melo
- Work item: FP-DOC-003

## Context

The public Foundry Pay repository contained a reusable protocol, reference
services, conformance tooling, and sanitized proof-of-work, but no explicit
license. Public visibility alone does not grant the permissions required for
open-source use, modification, and redistribution.

The repository history and provenance ledger identify the current
implementation as first-party work. No third-party source is recorded as copied
without a compatible license. External projects with unresolved licenses remain
reference-only.

## Decision

All content in the public Foundry Pay repository for which the licensor holds
the necessary rights is licensed under the Apache License, Version 2.0.

The copyright holder recorded in `NOTICE` is Renan Melo. Third-party materials
remain governed by their own licenses and attribution requirements. The
canonical Apache-2.0 text is stored unmodified in the root `LICENSE` file.

The license covers the public reference implementation, including:

- protocol schemas, canonicalization, and conformance vectors;
- Python and TypeScript reference implementations;
- deterministic authorization, signer, reconciliation, failure, and recovery
  components;
- fake executors, test harnesses, sanitized fixtures, documentation, and public
  evidence.

Apache-2.0 permits commercial use of this public work. The commercial boundary
is therefore an architectural and repository boundary, not an additional
restriction on the open-source license.

## Commercial boundary

Commercial Foundry Pay offerings may provide separable capabilities outside
this repository:

- hosted control-plane and production deployment;
- custody, HSM, MPC, key lifecycle, and signer operations;
- customer data, tenant configuration, and production credentials;
- proprietary risk policies and private connectors;
- managed observability, incident response, compliance, support, and service
  levels.

Those capabilities are not included merely by being described here. If any are
later contributed to this public repository by the rights holder without a
separate and explicit license notice, they fall under the repository's
Apache-2.0 license.

The Apache-2.0 license does not grant rights to Foundry Pay trade names,
trademarks, service marks, or product names except for customary attribution and
description of origin.

## Consequences

- External developers can use, modify, and redistribute the public work under
  one clear, OSI-approved license.
- Solana-Agent and Foundry Pay use compatible Apache-2.0 licensing while
  remaining independent products connected by a versioned protocol.
- Commercial differentiation depends on operation, integration, production
  security, and managed services rather than exclusive access to the protocol.
- Contributions intentionally submitted for inclusion are licensed under
  Apache-2.0 unless explicitly designated otherwise or governed by a separate
  agreement.
- Existing third-party obligations must be preserved. Unresolved-license
  material remains reference-only and must not be copied into the repository.
- Production and customer-sensitive assets stay outside the public repository.

## Alternatives considered

### License only the protocol package

Rejected because file-level mixed licensing would make reuse and contribution
harder to understand and would weaken the reference implementation as a public
good.

### Use a custom source-available license

Rejected because it would not provide a standard open-source grant and would
reduce compatibility with the surrounding ecosystem.

### Use a copyleft license

Rejected for the current phase because the project prioritizes broad protocol
adoption and compatibility with independent executors and commercial
integrations.

## Related documents

- `LICENSE`
- `NOTICE`
- `docs/PUBLIC_COMMERCIAL_BOUNDARY.md`
- `provenance/REUSE_LEDGER.yaml`
- `provenance/THIRD_PARTY_NOTICES.md`
- `docs/ADR/FP-ADR-001-external-first.md`
