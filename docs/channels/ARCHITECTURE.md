# Foundry Channels architecture

## System map

```text
Consumer UX
  sender app ─────────────── recipient link/QR ───────────── recipient app
      │                              │                            │
      │ signed intent/voucher        │ locator + client secret    │ wallet proof
      ▼                              ▼                            ▼
Foundry Pay Cloud (private, non-authoritative convenience)
  registry | resolver | relay | orchestrator | notifications | indexer
      │ closed public protocol objects; never free-form execution intent
      ▼
Foundry-Pay public (Apache-2.0)
  channel schemas | canonical bytes | voucher verifier | reference ledger
  execution protocol | authorization | reconciliation | failure lab | evidence
      │ EconomicPlan / PreparedExecution / ExecutionAuthorization / Receipt
      ▼
Solana-Agent public (Apache-2.0, independent)
  capability discovery | local policy | prepare | simulate | status | recover
      │ exact message commitment                  │ technical evidence
      ▼                                           ▼
external signer ── exact bytes ──► Solana RPC / validators
                                      │
                                      ▼
                         ChannelVault program + SPL Token Program
                                      │
                                      ▼
                         independent reconciliation sources
```

## Trust boundaries

1. Browser/link boundary: URLs leak through history, screenshots, forwarding,
   referrers, extensions, and compromised frontends.
2. Cloud boundary: operational databases are convenient but not rights
   authorities.
3. Public protocol boundary: canonical objects must be closed and versioned.
4. Executor boundary: Solana-Agent may implement local safety but not economic
   intent.
5. Signer boundary: only exact message bytes cross.
6. Chain boundary: programs enforce conservation; RPC responses are
   observations.
7. Reconciliation boundary: business completion requires independent
   comparison with the obligation.

## On-chain state

ChannelVault must store or derive:

- channel identity, program version, network genesis binding, and epoch;
- sender, mint, vault token account, and recipient claim public key;
- bound recipient wallet, if any;
- funded, activated-authorized, settled, and refunded totals;
- latest activated sequence and voucher hash;
- lifecycle status, channel expiry, voucher expiry, close request, and claim
  deadline;
- policy bounds required for enforcement;
- nonces or consumed identifiers required to prevent binding and settlement
  replay.

On-chain state is the economic enforcement authority.

## Off-chain state

May remain off-chain:

- human handles and receive-link resolution;
- encrypted claim delivery payloads and notification state;
- full signed voucher copies and friendly descriptions;
- Cloud orchestration jobs and UX sessions;
- RPC observations, reconciliation work, and evidence bundles;
- organization, billing, analytics, support, and proprietary risk data.

Off-chain state may accelerate or explain an operation. It cannot override the
ChannelVault state.

## Link data flow

### Receive link

`https://foundry.pay/renan`

Public human locator. It resolves to a signed profile or current receive
preference. It contains no claim secret and grants no value.

### Claim link

`https://foundry.pay/claim/<opaque-locator>#k=<claim-private-material>`

The path contains a random, non-sequential locator. Secret claim material is in
the URI fragment so it is processed client-side rather than included in the
HTTP request. Client code must still protect it from analytics, logs,
extensions, screenshots, and compromised frontend code.

The locator alone grants no right. The claim key plus a valid activated voucher
can bind a wallet.

### Persistent channel link

`https://foundry.pay/channel/<opaque-channel-locator>`

Public or access-controlled relationship view. It may resolve channel metadata
and current public status. It contains neither sender signing authority nor
claim private material.

## ChannelVault account model

```text
Channel PDA = PDA(
  "channel",
  sender_pubkey,
  mint_pubkey,
  channel_nonce_32
)

Vault ATA = associated token account(
  owner = Channel PDA,
  mint = channel mint
)
```

The random channel nonce prevents sender/mint enumeration from revealing all
relationships. The public channel account remains observable once known.

Programs are stateless; mutable channel state therefore lives in the Channel
PDA and tokens in its vault account. Token movement occurs through CPI with the
Channel PDA as signing authority.

## Critical accounting

At all times:

```text
funded_total = vault_balance + settled_total + refunded_total
settled_total <= activated_authorized_total <= funded_total - refunded_total
outstanding_right = activated_authorized_total - settled_total
unallocated_capacity = funded_total - refunded_total - activated_authorized_total
```

All amounts are unsigned base-unit strings at protocol boundaries and checked
integer values on-chain.

## Execution path

1. Public verifier validates channel, voucher, domain, signature, and requested
   delta.
2. Foundry creates an economic plan from authoritative state.
3. Solana-Agent advertises a matching channel capability.
4. Solana-Agent prepares and simulates a closed instruction.
5. Foundry verifies exact plan/message/simulation binding.
6. Foundry issues short-lived single-use execution authorization.
7. The signer signs only the prepared bytes.
8. Solana-Agent persists signature and broadcast intent, then submits once.
9. Unknown response becomes `needs_recovery`.
10. Status/recovery uses the persisted signature.
11. Foundry independently reconciles channel totals and token deltas.

## Availability without Cloud

Still usable:

- on-chain channel inspection;
- voucher and claim proof verification;
- destination binding;
- voucher activation;
- settlement, close-grace claims, and eligible refunds;
- status/recovery through any compatible client;
- independent evidence reconstruction from chain and signed artifacts.

Unavailable or degraded:

- human-handle resolution;
- notifications and link previews;
- relay sponsorship and orchestration;
- hosted indexing, analytics, and support context.

## Sources

- [Solana programs and state accounts](https://solana.com/docs/core/programs)
- [Solana Ed25519 precompile](https://solana.com/docs/core/programs/precompiles)
- [SPL Token CPI](https://solana.com/docs/tokens/advanced/cpi)
- [RFC 3986 URI syntax](https://datatracker.ietf.org/doc/html/rfc3986.html)
