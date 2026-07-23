# ExternalExecutionAgent Protocol

Version `0.1.0-draft`.

## Commands

- `prepare`
- `authorize-and-execute`
- `status`
- `recover`
- `evidence`

Commands exchange closed, versioned JSON objects. Free-form prompts are not a
protocol input.

## Correlation identifiers

- `execution_request_id`
- `idempotency_key`
- `obligation_id`
- `economic_plan_hash`
- `prepared_message_hash`
- `execution_commitment_hash`

## Hashing

Economic objects are normalized by a versioned Domain Normalization Profile and
canonicalized with RFC 8785 before SHA-256.

Protocol v1 uses:

```json
{
  "amount_base_units": "1000000",
  "network": "solana:devnet",
  "capability": "solana.spl_transfer.v1",
  "expires_at": "2026-07-23T18:00:00Z"
}
```

Financial values are decimal base-unit strings, never floats. Optional values
are absent rather than `null`. Signed objects reject floats, NaN, Infinity,
negative zero, and integers outside JavaScript's safe range. Addresses are
validated before hashing.

Unicode is not normalized silently: canonicalization hashes the exact input
sequence and rejects lone surrogates. Array order is material; object property
order is not.

The prepared message hash is SHA-256 over exact serialized transaction message
bytes, not a semantic reconstruction.

The execution commitment binds:

- protocol and normalization profile versions;
- request, obligation, and executor identity;
- economic plan hash;
- prepared message hash;
- simulation attestation hash;
- signer and execution constraints;
- authorization expiry.

## Recovery rule

If the executor may have broadcast but the response was lost, Foundry queries
`status(execution_request_id)` and independently observes the chain. The state
is `needs_recovery` while the outcome cannot be proven. A new message for the
same obligation is forbidden in that state.
