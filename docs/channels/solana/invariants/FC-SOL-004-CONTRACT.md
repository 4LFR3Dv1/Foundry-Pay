# FC-SOL-004 — Pure ChannelVault transition model

Status: ready  
Baseline dependency: FC-SOL-003A and FC-CTRL-027  
External review: not performed

## Objective

Implement an offline, deterministic transition model for the eight frozen
ChannelVault operations and validate its economic and lifecycle invariants with
property-based tests and bounded sequence exploration.

The model is not a Solana program. It contains no `AccountInfo`, entrypoint,
handler, CPI, SPL transfer, RPC, wallet, clock sysvar, or deployment.

## Model boundary

The model consumes explicit state, instruction, accounts, caller, and time. A
successful operation returns a complete projected post-state and one normative
success event. A rejected operation returns an error and leaves the complete
modeled pre-state unchanged.

Initialization models one atomic topology transition:

```text
channel owner: Absent | System
vault: absent
        ↓
channel owner: ChannelVault
vault owner: ClassicToken
space: 490
```

Any injected initialization failure returns the original topology.

## Required invariants

For every successful transition:

```text
settled <= activated
activated + refunded <= funded
funded, activated, settled, and refunded never decrease
```

And:

```text
sequence strictly advances
binding nonce is consumed at most once
recipient is immutable after binding
mint, vault, PDA, and token program are immutable
finalized is terminal
failure emits no success event and changes no modeled state
```

## Permissionless settlement

Settlement is independent of caller identity. It always derives:

```text
destination = canonical_ata(bound_recipient_wallet, mint)
```

`obligation_hash` is opaque caller-provided correlation material. It is not
economic authority, a recipient selector, or proof of business reconciliation.
Changing caller or correlation hash cannot change the economic post-state.

## Temporal boundaries

The harness tests:

```text
deadline = now + 899        → reject
deadline = now + 900        → accept
deadline = now + 2_592_000  → accept
deadline = now + 2_592_001  → reject
checked-add overflow        → reject
```

Activation is allowed only when `now < claim_deadline`. At or after the
deadline, new activation is blocked while settlement of activated rights
remains allowed. Voucher expiry blocks future activation but never extinguishes
an activated right.

## Exploration

The evidence must publish:

- generator seed and case count;
- bounded instruction/value/time domains;
- maximum depth;
- visited-state count;
- attempted, accepted, and rejected transition counts;
- state-deduplication rule;
- minimized counterexamples, if any.

The claim is limited to the published model and bounds. This work is not formal
verification and does not validate future runtime account borrowing, CPI
atomicity, SPL Token behavior, transaction scheduling, or deployment.
