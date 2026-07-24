# FC-ADR-004: Opaque links and claim-key recipient binding

- Status: accepted for devnet MVP
- Date: 2026-07-24
- Work item: `FOUNDATIONS-001`

## Context

A recipient may receive value before selecting a wallet. A link may be stolen,
forwarded, logged, enumerated, or opened through a compromised frontend. A
server-resolved locator alone must not authorize a destination.

## Decision

Three link types have separate authority:

1. Receive link: public human discovery, no value authority.
2. Claim link: random locator plus client-side claim private material.
3. Persistent channel link: relationship discovery/status, no signing secret.

The claim capability is an Ed25519 keypair generated client-side. ChannelVault
stores the claim public key. The private material is placed in the URI fragment
and must not be transmitted to the resolver, analytics, logs, or evidence.

Initial binding requires:

- claim-key signature over a closed `RecipientBinding`;
- destination-wallet signature over the same binding;
- matching channel, epoch, claim ID, network, program, nonce, and expiry;
- an unbound active channel.

After binding, the claim key alone cannot change the destination. Rebinding
requires signatures from both the current and new destination wallets and a
new monotonic binding nonce. V1 may disable rebind entirely until this flow is
implemented.

## Consequences

- The full claim link is a bearer capability and must be presented as money-like
  sensitive data.
- Locator enumeration alone yields no settlement authority.
- A compromised frontend that sees fragment material remains a critical threat;
  self-hosted or signed clients and explicit wallet previews are defense layers.
- Real-world identity is not proven by a bearer link. “Bob” means the holder of
  the claim capability who completes wallet binding.
- Optional out-of-band passcodes may add protection but are not normative v1
  authority.

## Rejected alternatives

- destination wallet in a mutable Cloud database;
- claim secret in path or query string;
- locator alone as a bearer right;
- sender-only destination changes after activation;
- claim-key-only rebind after initial binding.
