# FC-ADR-011: ChannelVault transition-model preflight

- Status: accepted
- Date: 2026-07-28
- Work item: `FC-CTRL-027`

## Context

FC-SOL-003A made the instruction registry operationally plausible without
implementing handlers. Two residual semantics must be explicit before the
transition harness becomes an oracle:

1. the `channel` account is absent or System-owned before initialization and
   ChannelVault-owned after successful initialization;
2. permissionless settlement lets the caller supply `amount` and
   `obligation_hash`, but neither caller identity nor correlation material may
   create authority or alter the beneficiary.

The existing FC-SOL-004 work item also used the phrase `formal harness` even
though the authorized implementation is property-based testing and bounded
state exploration.

## Decision 1 — ownership is a transition

The initialize account contract publishes distinct rules:

```text
pre-owner:
absent_or_system_owned_zero_data

post-owner:
foundry_channel_vault_program
```

All non-initialization instructions require the ChannelVault program owner in
both pre-state and post-state. The pure model treats PDA allocation and vault
creation as one atomic projected transition. An injected failure at any stage
returns the original topology and emits no success event.

This is a model property. It is not evidence that `invoke_signed`, rent, or ATA
CPIs have run in the Solana runtime.

## Decision 2 — settlement correlation is non-authoritative

`obligation_hash` is a caller-supplied opaque correlation value. It:

- is not signed economic authority;
- does not prove a business obligation;
- does not select the recipient or destination;
- does not affect `funded`, `activated`, `settled`, or `refunded`;
- must not be interpreted as reconciled business completion.

For equal state and amount, changing caller identity or `obligation_hash`
produces the same economic post-state. The only destination is the canonical
ATA derived from the already-bound recipient and immutable mint.

The on-chain event may preserve the opaque correlation value for indexing, but
consumers must treat it as untrusted caller-provided metadata.

## Decision 3 — validation claim

FC-SOL-004 uses:

- deterministic unit tests;
- property-based generation and shrinking;
- bounded breadth-first state exploration with state deduplication.

The permitted claim is:

> Bounded transition exploration and property-based validation found no
> violation within the published model and bounds.

The work is not formal verification and does not imply correctness of a future
Solana handler, CPI, token transfer, deployment, or runtime behavior.

## Consequences

- The executable account registry must publish pre- and post-owner rules.
- The transition model must ignore caller identity and `obligation_hash` in
  economic state evolution.
- External review remains `not_performed`.
- Local validator, devnet, mainnet, and real-value deployment remain blocked.
