# SA-CHAN-000 — draft capabilities and fake adapter

Status: ready for offline fixture implementation  
Solana/ChannelVault compatibility: not claimed  
External review: not performed

## Objective

SA-CHAN-000 defines a transport-independent seam between channel applications
and an executor-shaped component. It provides closed fixtures for product and
failure-flow development before real ChannelVault instruction contracts exist.

It is not SA-CHAN-001. It performs no capability discovery against a deployed
program and imports no Solana RPC, SDK, wallet, signer, IDL, or program runtime.

## Authority boundary

The caller supplies already-authorized economic intent. The fake adapter cannot
choose or alter:

- channel or epoch;
- sender or recipient;
- destination wallet;
- mint or network;
- amount or cumulative right;
- authorization lifetime.

The adapter may materialize deterministic fake bytes, expose status, simulate
loss and ambiguity, and return technical receipts. It cannot activate a right,
authorize signing, or declare economic completion.

```text
technical confirmation
!= independent observation
!= reconciled economic completion
```

## Closed surfaces

The implementation must publish versioned, closed contracts for:

- `ChannelCapabilityDescriptor`;
- `ChannelOperationRequest`;
- `PreparedChannelOperation`;
- `ChannelExecutionCommitment`;
- `ChannelOperationStatus`;
- `TechnicalChannelReceipt`;
- `ChannelRecoveryRequest`;
- `ChannelRecoveryResult`;
- `ReconciledChannelResult`.

Every material object binds its protocol version, capability ID, request ID,
operation ID, idempotency scope, exact prepared-material hash, executor ID,
expected authority, and expiry where applicable. Unknown fields, versions, and
capabilities fail closed without aliases or fallback.

Draft capability identifiers live under a fixture namespace and cannot use the
future real-operation identifiers as compatibility claims.

## Operation state

The fake state machine exposes:

```text
draft
→ prepared
→ authorized
→ submitted
→ confirmed
→ reconciled
```

Lateral and recovery states are:

```text
needs_recovery
needs_review
disputed
failed_definitive
```

`submitted` with a lost response becomes `needs_recovery`. Recovery never
creates a second submission automatically and never silently materializes new
bytes. A recovered technical identifier may advance to `confirmed`; only a
matching independent fixture observation may advance to `reconciled`.

## Adversarial fake scenarios

The adapter must select behavior explicitly; success is not the implicit
default. Required deterministic scenarios include:

- preparation only;
- authorization rejection;
- definitive pre-submission failure;
- accepted submission with receipt;
- accepted submission with lost response;
- unknown result after restart;
- technical identifier recovered after restart;
- technical confirmation without economic observation;
- exact matching reconciliation;
- observation mismatch;
- provider divergence;
- unsupported capability;
- unsupported version;
- changed exact-byte commitment;
- repeated request and idempotency conflict.

For the controlled fake runtime:

```text
submit intent count <= 1
automatic second submission count = 0
unknown never becomes reconciled without observation
```

This is not an exactly-once blockchain claim.

## Consumer fixtures

Fixtures may be consumed by a prototype UI to render honest states. They must
carry a visible limitation equivalent to:

> Fixture environment. No real assets. No production custody or security
> claim.

The fixtures cannot invent a simplified `success` state that collapses
`confirmed`, `reconciled`, `needs_review`, or `disputed`.

## Evidence and non-goals

Evidence covers the capability manifest, scenario matrix, exact commitments,
authority effects, restart/recovery, stable errors, and artifact hashes.

Stop if the work imports Solana execution, claims ChannelVault compatibility,
grants signing or economic authority, treats a technical receipt as payment
completion, retries an unknown result, advances SA-CHAN-001, or broadens any
deployment authorization.
