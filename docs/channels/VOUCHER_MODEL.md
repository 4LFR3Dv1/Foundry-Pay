# Cumulative voucher model

## Meaning

A `ChannelVoucher` is the sender's signed statement:

> For this exact channel, epoch, recipient claim key, mint, network, program,
> sequence, and expiry, I authorize a cumulative total of X base units.

It is not an additive payment.

```text
sequence 1 → cumulative total 10
sequence 2 → cumulative total 25
sequence 3 → cumulative total 40
```

The maximum right after sequence 3 activation is `40`, not `75`.

## Signed payload

```text
domain
protocol_version
environment
network
genesis_hash
program_id
channel_id
channel_account
epoch
sequence
previous_activated_voucher_hash
sender
recipient_claim_pubkey
mint
cumulative_authorized_base_units
issued_at
expires_at
```

`voucher_hash` is SHA-256 over canonical payload bytes. `sender_signature`
authenticates exactly those bytes.

## Issuance and activation

```text
draft
→ sender signs
→ issued
→ schema/hash/signature verified
→ submitted for activation
→ ChannelVault checks monotonic state and funding
→ activated
```

Only `activated` creates a settlement right.

This distinction resolves the stale-voucher problem:

- if sequence 3 is activated, sequence 1 or 2 fails the on-chain sequence and
  previous-hash checks;
- if sequence 3 is only issued, sequence 2 remains the latest activated right;
- the product must never present an issued-only amount as available to receive.

## Partial settlement

For `activated_authorized_total = 40` and `settled_total = 15`:

```text
remaining_right = 25
```

A settlement of 10 moves the totals to:

```text
settled_total = 25
remaining_right = 15
```

The voucher stays the same. The on-chain settled total prevents replay from
creating additional aggregate value.

## Sequence and epoch

- `sequence` starts at 1 and strictly increases.
- Gaps are permitted only if `previous_activated_voucher_hash` matches current
  state; a policy may require increments of exactly one.
- Cumulative total never decreases inside an epoch.
- Epoch advancement is a formal state transition after all prior outstanding
  rights are settled or explicitly expired.
- MVP may require opening a new channel instead of epoch advancement.

## Expiry

A voucher expiry:

- is a UTC instant with seconds precision;
- cannot exceed channel expiry;
- cannot be silently extended;
- remains enforced during closing;
- permits refund of residual outstanding value only after the claim deadline
  and expiry are both satisfied.

Clock-dependent decisions use the Solana Clock sysvar on-chain. Off-chain
display clocks are advisory.

## Validation order

1. closed schema and supported version;
2. domain, environment, network, genesis hash, program, and account;
3. sender, claim key, mint, channel, and epoch;
4. exact canonical hash;
5. sender signature;
6. expiry and lifecycle;
7. previous activated hash and monotonic sequence;
8. nondecreasing cumulative amount;
9. policy and funded-capacity bounds;
10. atomic state update.

Any failure is reject-without-effect.

## Negative cases

Mandatory negative vectors cover:

- cumulative decrease;
- repeated or lower sequence;
- wrong previous activated hash;
- wrong network/environment/program/channel/epoch;
- sender, recipient, or mint substitution;
- malformed amount or timestamp;
- total above funded capacity;
- expired voucher;
- mutated payload with stale hash/signature;
- old voucher after newer activation.

## Limitations

The foundation does not yet define:

- the exact Rust/Borsh instruction representation;
- production sender key custody;
- batched or compressed activation;
- offline proof that an issued voucher is globally latest.

Those are explicit future work, not hidden assumptions.
