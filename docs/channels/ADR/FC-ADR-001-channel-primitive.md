# FC-ADR-001: Funded cumulative unidirectional channel

- Status: accepted for devnet MVP
- Date: 2026-07-24
- Work item: `FOUNDATIONS-001`

## Context

The product needs a persistent transfer relationship that can receive several
value updates before settlement. A one-time payment link does not preserve the
relationship, while bidirectional or credit channels expand authority and
liquidity risk.

A purely off-chain sequence cannot make an older voucher globally invalid
unless a monotonic authority learns about the newer voucher.

## Decision

Version 1 uses one sender, one recipient, one SPL mint, and a funded
ChannelVault. Vouchers contain a monotonically increasing sequence and
cumulative authorized total within one epoch.

A voucher has two stages:

- `issued`: signed off-chain by the sender;
- `activated`: accepted as the latest state by ChannelVault.

Only activated state is settleable. Activation verifies the sender signature,
domain separation, channel identity, epoch, sequence, cumulative total,
recipient commitment, mint, network, program, expiry, funding, and previous
activated hash.

Settlement transfers at most:

```text
min(
  requested_amount,
  activated_authorized_total - settled_total,
  vault_balance reserved for activated rights
)
```

Partial settlements increase `settled_total`. They do not decrease the
cumulative authorized total.

## Consequences

- Old sequences are rejected after a newer sequence is activated.
- The Cloud can sponsor activation but cannot manufacture it.
- Value updates require an on-chain activation operation in v1.
- Issued-but-unactivated vouchers must be shown as pending, not received.
- No credit or underfunded entitlement exists.
- Epoch reset requires all prior rights settled or expired and formally
  finalized; the MVP may require a new channel instead.

## Rejected alternatives

- additive vouchers, because replay sums old effects;
- Cloud-only “latest voucher” registry, because outage or compromise changes
  rights;
- purely off-chain cumulative voucher as globally latest, because nonexistence
  of a newer voucher is not provable;
- bidirectional or underfunded channels, because they expand MVP risk.
