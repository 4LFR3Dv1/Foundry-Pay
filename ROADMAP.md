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

## Foundry Channels

The [Channels foundation](docs/channels/PROGRAM.md) freezes the first
consumer-facing primitive, authority model, cumulative voucher semantics,
public/private boundary, and smallest devnet vertical slice.

The first five implementation and validation items are defined in the
[Channels work graph](docs/channels/WORK_GRAPH.md). The first engineering PR is
an offline Channel/ChannelFunding validator; a Solana program and hosted Cloud
remain gated behind canonical byte, security, and conservation reviews.

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
