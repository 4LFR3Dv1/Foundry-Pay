# Channel Protocol

- Protocol version: `1.0.0-draft`
- Environment: `devnet`
- Network: `solana:devnet`
- Status: normative foundation, not implemented

## Domain objects

| Object | Purpose | Authority |
|---|---|---|
| `Channel` | authoritative lifecycle and accounting snapshot | ChannelVault |
| `ChannelFunding` | observed funding or top-up | ChannelVault + Token Program observation |
| `ChannelParticipant` | sender, claim key, or bound wallet role | ChannelVault |
| `ChannelPolicy` | immutable or versioned enforcement bounds | sender at open, enforced by ChannelVault |
| `ChannelVoucher` | signed cumulative sender authorization | sender; activated by ChannelVault |
| `RecipientBinding` | exact claim-key and wallet binding | claim key + wallet |
| `ChannelClaim` | non-secret delivery/status reference | relay convenience + channel evidence |
| `SettlementRequest` | requested delta against activated right | bound wallet + Foundry economic authority |
| `SettlementExecution` | correlated network execution state | Foundry + Solana-Agent journals |
| `SettlementReceipt` | reconciled settlement observation | ChannelVault + reconciler |
| `ChannelClosure` | frozen rights and close grace | sender request + ChannelVault |
| `ChannelRefund` | permitted return of unallocated/expired funds | ChannelVault |
| `ChannelEvidence` | hash-indexed claim/evidence manifest | evidence builder; independently verifiable |

Schemas live in `contracts/channel/`.

## Channel identity

`channel_id` is a protocol identifier. `channel_account` is the Solana PDA. All
signed channel objects bind both values plus:

- `domain`;
- `protocol_version`;
- `environment`;
- `network`;
- devnet `genesis_hash`;
- ChannelVault `program_id`;
- `epoch`;
- sender, recipient claim key, and mint as applicable.

This prevents a valid object from being replayed across deployments, networks,
programs, channels, epochs, recipients, or assets.

## Accounting

Let:

- `F` = funded total;
- `A` = latest activated cumulative authorized total;
- `S` = settled total;
- `R` = refunded total;
- `V` = current vault token balance.

Every accepted transition preserves:

```text
F = V + S + R
0 <= S <= A <= F - R
outstanding_right = A - S
unallocated_capacity = F - R - A
```

At activation:

```text
new_sequence > latest_activated_sequence
new_cumulative_total >= activated_authorized_total
new_cumulative_total <= funded_total - refunded_total
previous_activated_voucher_hash == latest_activated_voucher_hash
```

At settlement:

```text
requested > 0
settled_after = settled_before + requested
settled_after <= activated_authorized_total
requested <= vault_balance
destination == bound_recipient_wallet
```

At refund during closing:

```text
immediate_refund <= unallocated_capacity
```

Outstanding activated rights stay reserved until settled or their explicit
claim deadline and voucher expiry have passed.

## Required invariants

1. Cumulative authorization never decreases within one epoch.
2. Settled total never exceeds authorization, funding, policy, or capacity.
3. A lower or repeated activated sequence cannot add value.
4. A relay cannot mutate any signed voucher field.
5. Destination binding follows `RecipientBinding`.
6. Destination change is an explicit signed rebind or is disabled.
7. Claim capability and binding nonce are one-use.
8. Signatures bind domain, version, environment, network, program, channel,
   epoch, recipient, and asset.
9. Cross-environment, network, channel, version, recipient, and asset replay is
   rejected.
10. Unknown execution outcome forbids new broadcast.
11. Signer receives only exact bytes covered by execution authorization.
12. Secrets never enter public contracts, logs, prompts, fixtures, or evidence.
13. Critical execution and channel progress survives process restart.
14. Activated rights are provable from signed artifacts and chain state without
   a Cloud assertion.
15. Closing cannot invalidate unexpired outstanding activated rights.

## Operations

### Open

Creates Channel PDA and vault ATA with sender, mint, claim public key, policy,
expiry, genesis/latest hash, and zero accounting totals. Funding may be atomic
with open or transition through `funding`.

### Fund and top up

Transfers the fixed mint into the vault and increases `funded_total`. A top-up
does not increase `activated_authorized_total`.

### Activate voucher

Verifies sender Ed25519 signature through a transaction precompile instruction,
checks exact canonical voucher bytes, monotonic sequence/hash/amount, funding,
epoch, policy, and expiry, then stores the new activated state.

### Bind recipient

Verifies claim-key and destination-wallet signatures over one closed binding
payload. Initial binding is one-use. Rebind is disabled in the MVP unless the
current+new wallet flow is implemented.

### Settle

Transfers a requested positive delta to the bound wallet token account and
increments `settled_total`. A voucher may support multiple partial settlements,
but aggregate settlement cannot exceed its cumulative total.

### Inspect

Reads public channel state. A Cloud index is optional.

### Close

Freezes new activation and top-up, records the latest activated right and claim
deadline, permits settlement of reserved outstanding value, and exposes
unallocated excess for refund.

### Refund

Before the claim deadline, refunds only unallocated excess. After the deadline
and explicit voucher/channel expiry, refunds any remaining vault balance and
finalizes close.

## Canonicalization and hashing

Signed payloads:

- are closed JSON objects;
- use RFC 8785 JCS canonical bytes in off-chain protocol tooling;
- represent amounts as unsigned base-unit decimal strings;
- omit optional fields instead of using `null`;
- reject floats, NaN, Infinity, negative zero, unsafe integers, lone
  surrogates, unknown fields, and malformed timestamps/addresses.

```text
voucher_hash = SHA-256(JCS(channel_voucher_payload))
binding_hash = SHA-256(JCS(recipient_binding_payload))
```

On-chain instruction encodings must have a byte-for-byte normative mapping to
these payloads. The program must not rebuild semantic JSON. The future
cross-language work item will publish exact byte vectors for Python,
TypeScript, Rust, and the Ed25519 precompile instruction.

## No exactly-once claim

ChannelVault state transitions are atomic on-chain, but distributed submission
is not “exactly once.” The system promises durable intent, one controlled
broadcast attempt, replay-safe program transitions, status lookup, and
reconciliation.
