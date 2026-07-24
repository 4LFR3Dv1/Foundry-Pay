# FC-ADR-003: Public protocol and private operated product

- Status: accepted
- Date: 2026-07-24
- Work item: `FOUNDATIONS-001`

## Context

Foundry Channels must remain independently verifiable and integrable while
Foundry Pay retains a viable hosted product. The Solana-Agent kernel is already
an independent public good.

## Decision

The public Foundry-Pay repository contains Apache-2.0:

- channel schemas, canonicalization, hashes, verifier behavior, and vectors;
- public SDKs and deterministic examples;
- reference authorization, ledger, reconciliation, failure, and evidence
  implementations;
- ChannelVault source, IDL, tests, and upgrade policy when implemented.

Solana-Agent remains an independent Apache-2.0 repository. Integration uses
versioned capabilities and the External Execution Protocol.

Private Foundry Pay Cloud contains:

- hosted control plane, accounts, organizations, API keys, and billing;
- customer data/configuration and proprietary risk policy;
- enterprise connectors, operations, notifications, analytics, observability,
  custody configuration, support, and SLAs.

The private layer may narrow operations and provide convenience. It cannot
redefine public signed objects, broaden authority, or become the only verifier
or recovery path.

## Consequences

- Public and private code have separate repositories and release identities.
- Private services import released public packages rather than copying them.
- Public conformance must be sufficient for external executors and clients.
- Commercial differentiation is operated security and integration, not
exclusive protocol knowledge.

## Rejected alternatives

- absorb Solana-Agent;
- publish Cloud infrastructure or customer configuration;
- keep verifier or ChannelVault contracts private;
- use custom restrictions to narrow Apache-2.0 rights.
