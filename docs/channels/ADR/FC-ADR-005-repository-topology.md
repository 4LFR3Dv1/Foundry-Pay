# FC-ADR-005: Namespaced public channel program

- Status: accepted
- Date: 2026-07-24
- Work item: `FOUNDATIONS-001`

## Context

The current repositories already contain functioning kernels and governance.
Creating a new repository or pre-creating many empty packages would fragment
history and complicate local development.

## Decision

Foundry Channels begins inside public Foundry-Pay:

```text
docs/channels/
contracts/channel/
```

The first implementation package will be:

```text
packages/channel-protocol/
```

Create `programs/foundry-channel-vault/` only in the explicitly authorized
Solana-program work item. Split Python/TypeScript SDKs, verifier, and reference
ledger packages only when stable consumer or release boundaries justify it.

Solana-Agent gains generic capability descriptors and channel adapters in its
own repository. Private Cloud code stays in `foundry-pay-platform`.

## Consequences

- Existing Foundry protocol, authorization, reconciliation, and failure tooling
  can be reused without moving code.
- New public contracts are discoverable but do not rename current packages.
- Repository boundaries map to authority and licensing boundaries.
- Cross-repository changes require separate PRs linked by immutable commits and
  conformance evidence.

## Rejected alternatives

- a third public `Foundry-Channels` repository at foundation time;
- importing the Solana-Agent kernel;
- placing private Cloud stubs in the public repository;
- scaffolding all proposed packages before a verified consumer exists.
