# Failure and recovery

## Guarantee

Foundry Channels does not claim distributed exactly-once execution.

It targets:

> Durable economic intent, replay-safe on-chain effects, one controlled
> broadcast attempt, consultable status, signature-based recovery, and
> independent reconciliation.

## Durable order

For each network mutation:

```text
economic request persisted
→ prepared exact message persisted
→ simulation and commitment persisted
→ execution authorization persisted
→ exact signature persisted
→ broadcast intent persisted
→ provider called once
→ response or uncertainty persisted
→ recovery by signature
→ independent reconciliation
```

No later stage may be inferred when its evidence is missing.

## Channel-specific ambiguity

### Open/fund ambiguity

Query Channel PDA and vault account. Do not create another channel or transfer
funding until the original channel nonce/account and signature are reconciled.

### Voucher activation ambiguity

Inspect `latest_activated_sequence` and voucher hash. If they match, activation
succeeded. If a lower sequence remains after transaction expiry and signature
is proven absent, a new prepared transaction may be reviewed. Never assume an
RPC error means the voucher was not activated.

### Binding ambiguity

Inspect the bound wallet and binding nonce. Do not submit a second binding with
a different wallet. Any mismatch becomes `needs_review`.

### Settlement ambiguity

Recover the persisted signature, then inspect:

- Channel `settled_total`;
- vault token balance;
- recipient token balance;
- transaction status and logs;
- voucher hash and sequence.

A second settlement message is forbidden until the requested delta is
reconciled.

### Close/refund ambiguity

Inspect channel lifecycle, claim deadline, final activated right, refunded
total, vault balance, and signature. Before the deadline, refund must be zero
because a signed voucher may still be presented. Never repeat a refund based
only on a missing response.

## Recovery states

| State | Meaning | Automatic mutation |
|---|---|---:|
| `failed` | proven failure before external acceptance | forbidden; explicit new plan may be reviewed |
| `rejected` | validation/policy/program denied with no effect | forbidden |
| `needs_recovery` | signature or broadcast may have produced effect | forbidden |
| `needs_review` | evidence is insufficient or materially inconsistent | forbidden |
| `disputed` | authoritative observations disagree | forbidden |
| `completed` | expected on-chain effect independently reconciled | none |

## RPC and blockhash

- Store the signature and signed transaction before `sendTransaction`.
- Use no client-side blind retries for effectful gateway submission.
- A live-blockhash `not found` result is ambiguous.
- Blockhash expiry does not erase an already broadcast transaction effect.
- After expiry, “not found” still requires independent reconciliation before
  rematerialization.
- Divergent RPC providers preserve all observations and open review.

## Cloud outage

### Cloud service unavailable

Clients use public schemas/SDKs, signed artifacts, Channel account, and a
compatible executor. Human-handle resolution and notifications may fail.

### Cloud database lost

Rebuild public channel state from on-chain accounts/events and user-exported
signed artifacts. Operational delivery history may be irrecoverable. The
database must never be the only copy of an activated right.

### Frontend compromised

Stop link processing and signing. Compare displayed channel/program/mint/wallet
with wallet-native previews and public explorers. A frontend that reads claim
fragment material can steal the bearer capability; rotate only before binding
and activation rights permit. After binding, claim key alone cannot redirect.

## Evidence required

Every recovery bundle should contain hashes or sanitized references for:

- channel/voucher/binding/settlement objects;
- execution request, prepared message, simulation, commitment, authorization;
- signer receipt and persisted transaction signature;
- gateway/executor journal events;
- transaction status and Channel account snapshots;
- vault/recipient token observations;
- reconciliation source identities and disagreement fields;
- final decision and remaining uncertainty.

Private claim material, keys, credentials, and customer data are excluded.

## Reuse

The existing Foundry failure lab and Solana-Agent chaos gateway already prove:

- signature-first persistence;
- response-loss recovery;
- no automatic redispatch from a reserved request;
- restart behavior;
- at-most-one controlled provider call in modeled scenarios;
- L1/L2 disagreement preservation.

Channel-specific account and accounting assertions must be added; the kernels
do not need rewriting.

## Official reference

[Solana transaction confirmation and expiration](https://solana.com/uk/developers/guides/advanced/confirmation)
documents blockhash lifetime and RPC lag considerations. Foundry Channels adds
the stricter local rule that ambiguity never authorizes a second broadcast.
