# FC-SEC-002 Version, rotation, revocation, and migration policy

Status: normative for the offline protocol v1 model.

## Fail-closed version selection

An object is verified only by the exact `(object_type, profile_id, domain,
protocol_version)` verifier selected by its consuming operation.

Unknown or unsupported values are rejected before signed-preimage verification:

```text
unknown protocol_version -> version_verification / unsupported_version
unknown profile_id       -> profile_verification / unsupported_profile
wrong object domain      -> domain_verification / domain_mismatch
wrong authority type     -> type_verification / object_type_mismatch
```

A verifier must not:

- remove unknown fields and retry;
- reinterpret a new object as v1;
- fall back from an unknown profile;
- try several domains until one accepts;
- rewrite an object into an older form;
- treat a record hash as an authority signature.

## Rotation

Already-issued signed bytes do not rotate. A change to a Program ID, signing
authority, profile, protocol version, environment, network, genesis hash, mint,
channel, or epoch creates a different authority context.

Protocol v1 uses the conservative policy:

```text
channel + epoch
-> fixed protocol version
-> fixed hash profile
-> fixed domain
-> fixed program and network context
```

A future rotation is eligible only through a new channel or new epoch whose
authoritative state explicitly records the new context. FC-SEC-002 does not
implement that on-chain transition.

## Revocation

The Cloud cannot make a valid cryptographic signature mathematically invalid by
statement or database mutation. Economic eligibility may end only through a
verifiable protocol condition, including:

- a voucher is superseded by a higher accepted sequence;
- a binding nonce has already been consumed;
- a pre-activation deadline has expired;
- an epoch has advanced;
- a channel has been finalized;
- an on-chain policy has disabled a program/version in a future implementation.

Activated rights do not expire economically in protocol v1. They remain
reserved until reconciled settlement.

No Cloud-controlled revocation list is introduced by this work item.

## Migration

Objects are never rewritten in transit:

```text
v1 input -> v1 verification or rejection
v2 input -> v2 verification or unsupported_version
```

Migration of a live channel is not implemented. A future migration requires a
separate ADR, authoritative state transition, compatibility vectors, and
cross-language conformance. Until then, a new version requires a new channel or
epoch.

## Rejection effects

Rejection may append a bounded audit event. It must not:

- advance verified, activation-requested, authorized, or completed state;
- consume a binding nonce or execution authorization;
- alter a normative sequence or previous-object hash;
- change channel lifecycle;
- create or extinguish an economic right;
- move or reconcile value.

The exact allowlist is maintained in
`state-surface-taxonomy.yaml`.

## Scope limitation

This policy proves offline verifier behavior. It does not prove ChannelVault,
Solana transaction-signature, RPC, wallet, devnet, mainnet, or production
behavior.
