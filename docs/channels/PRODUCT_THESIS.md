# Product thesis

## Thesis

> Links can represent persistent channels for transferring value.

Current crypto payment flows repeatedly ask a sender for a wallet address,
network, asset, and amount. Foundry Channels creates a reusable relationship:

> Open a channel. Share a link. Send as often as you want.

The link is the discovery and delivery surface. The economic right is a signed,
domain-separated, cumulative voucher enforced by funded on-chain state.

## User jobs

### Sender

- fund a relationship once;
- increase the cumulative amount without asking for a destination wallet each
  time;
- know how much is funded, authorized, settled, reserved, and refundable;
- stop future updates without stealing already activated recipient rights;
- recover safely when the network response is ambiguous.

### Recipient

- receive before selecting a destination wallet;
- bind an existing wallet explicitly;
- see a plain-language amount and expiry;
- settle partially or fully;
- prove the right without trusting a Cloud database assertion;
- recover using the claim capability, signed voucher, and on-chain state.

## Primitive

Version 1 is:

- unidirectional;
- funded before authorization;
- single-sender and single-recipient;
- cumulative within an epoch;
- activated monotonically on-chain;
- partially or fully settleable;
- reusable until close or expiry.

For a channel with:

```text
funded_total = 100
activated_authorized_total = 40
settled_total = 15
refunded_total = 0
```

the current rights are:

```text
liquidatable_now = 40 - 15 = 25
unallocated_capacity = 100 - 40 = 60
vault_balance = 100 - 15 = 85
```

Only `25` is currently owed. The other `60` remains sender-controlled capacity.

## Issued versus activated

A sender can create many signed vouchers off-chain. An off-chain verifier cannot
prove that a later voucher does or does not exist. Therefore:

- `issued`: correctly signed by the sender but not yet reflected in ChannelVault;
- `activated`: accepted by ChannelVault as the channel's latest monotonic
  sequence and cumulative authorized total.

Only activated state creates a settlement right in v1. The relay can submit
activation but cannot sign it. A sender or recipient can submit it through any
compatible client if the Cloud is unavailable.

This adds a network operation to value updates, but removes an otherwise
unavoidable ambiguity around stale vouchers and sender revocation.

## Value proposition

| Existing friction | Foundry Channels behavior |
|---|---|
| Ask for a wallet on every payment | Reuse one relationship |
| Recipient has no wallet selected | Bind after receiving the protected claim |
| Several transfers cause several settlements | Increase one cumulative total |
| Lost RPC response risks blind retry | Recover by persisted signature |
| Hosted ledger asserts entitlement | Verify signed voucher and on-chain channel |
| Sender closes and surprises recipient | Outstanding activated rights survive closing |

## Consumer language

Primary UI terms:

- Channel
- Available
- Sent
- Received
- Ready to receive
- Choose wallet
- Transfer
- Recovering
- Close channel

Protocol terms such as PDA, canonicalization, execution commitment, RPC,
voucher epoch, and reconciliation source belong in developer and operations
surfaces, not the consumer flow.

## Success criteria for the first proof

- a new user explains the product in 30 seconds;
- a sender understands funded versus sent versus still available;
- a recipient binds the intended wallet without copying an address to the
  sender;
- 10 → 25 → 40 is understood as one cumulative entitlement, not 75;
- an RPC response loss shows “recovering”, never a second payment attempt;
- both parties can verify channel and settlement state from public artifacts.

## Non-goals

Foundry Channels v1 is not:

- a Lightning-style bidirectional network;
- a credit instrument or underfunded promise;
- a wallet or custody provider;
- a private balance database;
- a streaming, swap, bridge, routing, or liquidity protocol;
- a mainnet-ready payment product.
