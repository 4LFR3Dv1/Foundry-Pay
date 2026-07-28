# FC-SEC-004 — Offline concurrency and linearizability

Status: ready  
Dependencies: FC-PROTO-004, FC-SOL-004, FC-CTRL-030  
External review: not performed

## Objective

Demonstrate that concurrent settlement and lifecycle candidates are
linearizable in a versioned offline model and that stale snapshots cannot
produce oversettlement, over-refund, lost activated rights, or premature
finalization.

This work does not model or prove Solana account locking, transaction
scheduling, CPI atomicity, token transfers, validator behavior, RPC, or
deployment.

## Versioned model

```text
prepare(state at version N, operation, observed time)
→ CandidateTransition(read_version=N, projected transition)

commit(candidate, authoritative commit time)
→ revalidate version, duplicate operation ID, lifecycle, time, and economics
→ accept only if current_version == N
→ increment version exactly once
```

A stale candidate is rejected without changing state, accepted operation IDs,
history, or version. Retrying requires an explicit new prepare against the
current state.

## Serial witness

Every accepted commit appends:

```text
operation_id
operation
commit_time
version_before
version_after
```

The harness must replay that ordered history from the initial state and obtain
the exact current state and version. Final invariant checks alone are
insufficient.

## Time

Preparation never grants durable temporal authority. The FC-SOL-004 transition
function is invoked again at commit using the authoritative commit time.

An activation prepared at `deadline - 1` and committed at `deadline` rejects.

## Duplicate and stale operations

```text
same operation_id
→ at most one accepted economic effect

same snapshot, different operation IDs
→ at most one direct commit
→ other candidates become stale
→ they may advance only after explicit re-preparation
```

Idempotency and conservation are separate: distinct IDs can represent distinct
requests but never exceed the currently activated right.

## Required race matrix

- two partial or full settlements;
- duplicate settlement ID and distinct IDs;
- refund versus settlement;
- activation versus refund;
- activation versus exclusive deadline;
- settlement versus finalize;
- refund versus finalize;
- close versus activation;
- same and competing activation sequences.

## Additional accounting property

The model derives:

```text
vault_balance = funded - refunded - settled
vault_balance + settled + refunded = funded
```

This is internal model accounting. It does not compare against a real SPL Token
account.

## Permitted claim

> Concurrent settlement and lifecycle interleavings were checked for
> linearizability, conservation, and stale-snapshot rejection within the
> published offline model.

This is not formal verification and is not a ChannelVault runtime race-safety
claim.
