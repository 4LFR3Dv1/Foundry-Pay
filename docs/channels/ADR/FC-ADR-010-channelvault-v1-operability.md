# FC-ADR-010: ChannelVault v1 initialization, permissionless settlement, and close window

- Status: accepted
- Date: 2026-07-28
- Work item: `FC-SOL-003A`

## Context

FC-SOL-003 froze deterministic instruction bytes and most account-meta rules,
but an implementability review found three decisions that must be explicit
before property testing or publication through Solana-Agent:

1. an absent program-owned PDA cannot be initialized without the System Program;
2. the `settle` account list has no recipient signer, while an older design
   document described recipient approval;
3. the sender-selected claim deadline had no minimum or maximum window.

No ChannelVault handler, deployment, or external consumer exists, so this is a
coordinated pre-runtime correction. Instruction payload bytes, discriminators,
canonical protocol preimages, the 490-byte account layout, PDA seeds, and
Ed25519 layouts remain unchanged.

## Decision 1 — atomic channel and vault creation

`initialize_channel` creates both the `ChannelState` PDA and its canonical
classic SPL Token associated token account in one atomic instruction.

The account contract contains:

```text
channel                  writable, expected PDA, absent/system-owned before creation
sender                   writable signer and rent payer
mint                     read-only classic SPL Token mint
vault                    writable canonical ATA(channel PDA, mint)
system_program           executable, exact System Program ID
token_program            executable, exact classic SPL Token Program ID
associated_token_program executable, exact Associated Token Program ID
```

The future handler must:

- calculate rent for the exact 490-byte account at runtime;
- create and assign the PDA with a System Program CPI using `invoke_signed`;
- create the canonical vault ATA idempotently through the Associated Token
  Program;
- reject substituted programs, PDA, mint, vault, owner, or authority;
- complete all validation before emitting `ChannelInitialized`.

The sender is the v1 payer. A separate payer is deferred.

## Decision 2 — permissionless settlement

Protocol v1 settlement is permissionless after recipient binding. No caller or
recipient transaction signature is required by the ChannelVault instruction.

The caller cannot choose the economic beneficiary. The handler must derive and
validate:

```text
recipient_token_account
= canonical ATA(bound_recipient_wallet, channel.mint)
```

It must also preserve:

```text
requested > 0
settled_after = settled_before + requested
settled_after <= activated_authorized_total
requested <= vault balance
mint and classic token program match the channel
```

Anyone may pay the transaction fee or act as keeper, but no caller can redirect
value, change the amount encoded in the instruction, create a right, or satisfy
a business obligation by assertion. `SettlementExecuted` remains an on-chain
fact, not business reconciliation.

## Decision 3 — bounded exclusive claim window

Protocol v1 uses fixed experimental bounds:

```text
MIN_CLAIM_WINDOW_SECONDS = 900
MAX_CLAIM_WINDOW_SECONDS = 2_592_000

minimum_deadline = now.checked_add(MIN_CLAIM_WINDOW_SECONDS)
maximum_deadline = now.checked_add(MAX_CLAIM_WINDOW_SECONDS)

minimum_deadline <= claim_deadline <= maximum_deadline
```

`now` comes from the Solana Clock in a future handler and is an explicit,
injected value in pure tests. Arithmetic overflow rejects.

The deadline remains exclusive:

```text
now < claim_deadline  → activation may proceed
now >= claim_deadline → activation is frozen
```

These are experimental protocol constants, not a production UX claim. Changing
them requires a versioned decision and regenerated fixtures.

## Consequences

- FC-SOL-004 and SA-CHAN-001 remain blocked until FC-SOL-003A updates and
  republishes the exact account-meta registry.
- FC-SOL-005 and FC-FAIL-003 may continue because their current contracts do
  not depend on the corrected initialization metas.
- No handler, CPI, transfer, local-validator execution, or deployment is
  authorized by this decision.
- External Solana review remains `not_performed`.

