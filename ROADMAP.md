# Roadmap

Foundry Pay is a pre-alpha public reference implementation. Roadmap entries are
directional until represented by an active work item in `docs/WORK_GRAPH.md`.

## Demonstrated

- External Execution Protocol schemas and cross-language canonicalization;
- short-lived, single-use exact-message authorization;
- isolated signing boundary;
- governed Solana devnet remediation;
- L1/L2 reconciliation;
- deterministic and real-process recovery matrices;
- sanitized, hash-bound evidence.

## Next

- stabilize protocol errors, capabilities, and version negotiation;
- publish correlated journal and evidence manifest contracts;
- formalize simulation validity and drift handling;
- improve package-level quickstarts and executor conformance tooling;
- obtain independent external verification of the public onboarding flow.

## Before a production claim

- complete an independent security review;
- add production-grade custody and signer infrastructure outside this
  reference repository;
- demonstrate sustained operation and incident response;
- add L3 or equivalent independent observations;
- define versioning, migrations, support policy, and release process;
- complete mainnet readiness review and explicit operational approval.

Completion of a roadmap item must be supported by tests, evidence, provenance,
and the work graph. This document does not promise dates or service levels.
