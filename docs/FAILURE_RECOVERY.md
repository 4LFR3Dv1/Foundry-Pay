# Distributed Failure Recovery

FP-FAIL-001 proves the safety behavior between authorization, durable signing,
broadcast, recovery, and independent reconciliation. It does not claim
`exactly once`. The guarantee is:

> Repeatable delivery, an idempotent economic effect where the rail permits it,
> a consultable durable state, and no automatic retry from uncertainty.

## Durable ordering

The executor must persist these boundaries in order:

```text
authorization accepted
→ exact signature persisted
→ broadcast intent persisted
→ provider invoked at most once
→ response or uncertainty persisted
→ recovery by the persisted signature
```

`broadcast_count` records the durable broadcast intent before the external call.
`provider_broadcast_calls` is the injected provider's independent call counter.
This distinction exposes the crash window between write-ahead intent and the
network invocation.

## State model

| State | Meaning | Automatic broadcast | New preparation |
|---|---|---:|---:|
| `authorized` | No signature or broadcast exists | forbidden | same execution may resume |
| `signed` | Exact signed transaction is durable | operator-controlled first attempt | forbidden for another message |
| `broadcast_in_flight` | Write-ahead broadcast intent exists | forbidden after restart | forbidden |
| `needs_recovery` | Broadcast outcome is ambiguous | forbidden | forbidden |
| `broadcast_failed_known` | Provider proved non-acceptance | forbidden | permitted by policy |
| `expired_requires_new_prepare` | Blockhash expired before any broadcast intent | forbidden | required |
| `confirmed` | Signature was observed as confirmed | forbidden | forbidden; obligation is settled |

Blockhash expiry never resolves uncertainty. If the blockhash expires while an
operation is `needs_recovery`, the state remains `needs_recovery` until an
observer establishes whether the persisted signature produced an effect.

## Fault matrix

### Response lost after broadcast

The simulated provider persists the economic effect and loses the response. The
executor records `needs_recovery`, restarts, queries the persisted signature,
and transitions to `confirmed`. Provider call count and economic effect count
remain exactly one.

### Restart before signature persistence

An injected crash occurs before the signature journal transaction. After
restart, state remains `authorized`, no signature exists, and both durable
broadcast count and provider call count are zero.

### Restart after signature persistence

After restart, the exact signature and signed-transaction hash remain present.
No broadcast has occurred. A different transaction cannot be substituted.

### RPC unavailable

The broadcast outcome is unknown and the recovery observer is unavailable.
Recovery returns `needs_recovery`; it does not retransmit, rematerialize, or
declare failure.

### Broadcast outcome unknown

Neither the transport nor observer can establish acceptance. Automatic execute
is rejected from `needs_recovery`, even after blockhash expiry.

### Blockhash expired

When expiry is detected before a broadcast intent, the executor records
`expired_requires_new_prepare` and makes no provider call. Any new Solana
message requires preparation, simulation, commitment, and authorization again.

### L1/L2 divergence

Two internally valid observations disagree about the balance delta. Execution
status remains the status supported by the matching L1 source, while
reconciliation becomes `reconciliation_disputed` and independent verification
becomes `disputed`. The system never broadcasts a correction automatically.

## Evidence integrity

Each journal event contains the previous event hash and is hashed over canonical
JSON. Evidence generation verifies the chain before writing a scenario report.
The manifest hashes every report and records:

- exact implementation commit;
- scenario count;
- whether every broadcast count is at most one;
- whether every unresolved outcome forbids rematerialization.

The matrix is deterministic and uses only synthetic identifiers plus the
already-sanitized FP-E2E-001/FP-REC-001 evidence for the divergence case.

## Verification

```text
python -m pytest tests/failures -q
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
```
