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
- `execution_request_id`, `obligation_id`, and executor identity;
- economic plan hash;
- prepared message hash;
- simulation attestation hash;
- signer and execution constraints;
- authorization expiry.

### Draft v1 pre-integration correction

`FP-PROTO-007` made `obligation_id` an explicit required property of the
normative execution commitment. No released consumer used the earlier draft.
The correction aligns Foundry Pay with the first live Solana-Agent
implementation and keeps protocol version `1.0.0`.

Changing, omitting, or supplying a non-canonical `obligation_id` invalidates the
commitment. `PreparedExecution` does not duplicate the obligation identifier;
Foundry reconstructs the commitment using its authoritative economic plan and
the prepared fields returned by the executor.

## Foundry execution authorization

`FP-AUTH-001` makes Foundry the authorization authority for the COMMIT phase.
Foundry accepts only a closed `PreparedExecution`, then independently:

1. normalizes the authoritative economic plan and recalculates
   `economic_plan_hash`;
2. decodes the prepared message and hashes its exact bytes;
3. recalculates `simulation_attestation_hash`;
4. reconstructs the normative commitment with the authoritative
   `obligation_id`;
5. verifies the request, executor, signer, constraints, fee, program allowlist,
   simulation success, and all expiry bounds;
6. emits a short-lived `ExecutionAuthorization` bound to those exact hashes.

Authorization authenticity is supplied through an injected signing interface.
The authorization service contains no Solana key, transaction-signing, RPC, or
broadcast capability. A production authority may place its authorization key
behind an HSM or KMS without giving Foundry access to a Solana asset key.

Emissions and consumptions are persisted in a SQLite journal. At most one
authorization may be active for the same request or obligation. Reissuing the
same authorization is idempotent; a competing grant is rejected. Consumption
is single-use, survives process restart, and rejects replay or expiry.

## Recovery rule

If the executor may have broadcast but the response was lost, Foundry queries
`status(execution_request_id)` and independently observes the chain. The state
is `needs_recovery` while the outcome cannot be proven. A new message for the
same obligation is forbidden in that state.

## Fake executor conformance model

The reference fake executor uses a persistent SQLite journal and a test-only
HMAC authorization authority. HMAC is not the production signer design; it
exists only to make authenticity, expiry, exact binding, and single-use
behavior deterministic in conformance tests.

Within one immediate SQLite transaction, the fake executor:

1. validates authorization authenticity, time bounds, and exact binding;
2. records the unique authorization consumption;
3. applies a unique effect keyed by `obligation_id`;
4. persists the technical receipt and `confirmed` state;
5. commits;
6. only then returns the response.

The `after_commit_before_response` fault raises after step 5. A new executor
process opens the same journal, finds the receipt, and returns a confirmed
recovery result. Replaying the authorization or preparing another request for
the completed obligation fails without increasing the effect count.

Before applying an effect, COMMIT recalculates:

- SHA-256 of the persisted exact message bytes;
- simulation attestation hash;
- execution commitment hash;
- authorization binding to request, message, commitment, and signer.
