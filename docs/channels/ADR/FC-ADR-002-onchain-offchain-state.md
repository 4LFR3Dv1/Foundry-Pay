# FC-ADR-002: On-chain economic state, off-chain convenience state

- Status: accepted for devnet MVP
- Date: 2026-07-24
- Work item: `FOUNDATIONS-001`

## Context

Foundry Pay Cloud improves discovery and UX but may be unavailable,
compromised, or lose its operational database. A recipient right cannot depend
only on a hosted assertion.

## Decision

ChannelVault is authoritative for:

- channel identity, version, epoch, sender, mint, and lifecycle;
- claim public key and bound destination wallet;
- funded, activated-authorized, settled, and refunded totals;
- latest activated sequence and voucher hash;
- expiry, close grace, and enforcement policy.

SPL tokens remain in a vault token account controlled by the Channel PDA.

Cloud and public off-chain tools may store:

- human handles, opaque link locators, delivery, and notification state;
- signed vouchers and encrypted claim payloads;
- orchestration, RPC observations, reconciliation jobs, and evidence;
- private customer, organization, analytics, risk, and support state.

Cloud state cannot override ChannelVault. A signed object is independently
verifiable but becomes a settlement right only under the activation rule in
FC-ADR-001.

## Consequences

- Cloud loss degrades discovery and convenience, not activated rights.
- A claimant must retain or export claim material and relevant signed objects.
- A public SDK must support direct inspection, binding, activation, settlement,
  and recovery.
- Relationship metadata remains observable once a channel address is known;
  random nonces and opaque locators reduce enumeration but do not create chain
  privacy.

## Rejected alternatives

- Cloud database as balance authority;
- storing PII or human handles on-chain;
- storing claim private material on-chain or in public evidence;
- trusting an executor receipt as business settlement.
