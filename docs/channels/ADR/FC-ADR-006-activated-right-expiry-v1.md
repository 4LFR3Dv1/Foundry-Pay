# FC-ADR-006: Activated rights do not expire economically in protocol v1

- Status: accepted
- Date: 2026-07-26
- Work item: `FC-PROTO-005`

## Context

Foundry Channels uses cumulative authorization and preserves:

```text
F = V + S + R
0 <= S <= A <= F - R
outstanding = A - S
```

Where:

- `F` is total funded;
- `V` is the observed vault balance;
- `S` is total economically reconciled settlement;
- `R` is total economically reconciled refund;
- `A` is the latest activated cumulative authorization.

Voucher expiry already prevents an unactivated voucher from being activated.
Treating expiry as extinguishing an activated right would either reduce `A`,
breaking cumulative monotonicity, or permit `R` to grow beyond the existing
capacity bound. Protocol v1 has no explicit accounting variable for formally
extinguished activated rights.

## Decision

In protocol v1:

```text
unactivated voucher expired
→ activation is forbidden

activated right reached voucher or channel expiry
→ no economic state change
→ A is unchanged
→ outstanding is unchanged
→ refundable capacity is unchanged

activated right
→ remains reserved until reconciled settlement

final close
→ requires outstanding == 0
```

`expired_outstanding_right` is not a valid refund reason in v1.

No Cloud record, technical receipt, local clock, missing response, channel
expiry, or voucher expiry may extinguish an activated economic right.

## Closure snapshots

A close request does not freeze the final activated total. Voucher activation
remains possible during the claim window, so the protocol distinguishes:

```text
ClosureSnapshotAtRequest
ClosureSnapshotAtFreeze
```

The request snapshot records `A_request`, `S_request`, `R_request`, `V_request`,
the latest activated sequence and hash, `requested_at`, and the exclusive claim
deadline.

At or after the deadline, a new authoritative snapshot freezes `A_final` and
the final activated sequence and hash. Refund projection must use the freeze
snapshot:

```text
excess_refundable = F_final - R_at_freeze - A_final
```

It must never use `A_request`.

## Exclusive deadline

The claim deadline is exclusive for activation:

```text
now < claim_deadline
→ activation may proceed under all normal voucher checks

now >= claim_deadline
→ activation is forbidden
→ freeze may be evaluated
→ refund may be evaluated
```

`now` is an explicit runtime input or comes from an injected testable clock.
The offline runtime does not implicitly consult wall-clock time and does not
claim Solana Clock provenance.

Voucher `issued_at` remains descriptive. It is not proof of signature creation
time and is not a close-window eligibility cutoff.

## Refund semantics

Before the exclusive deadline:

```text
refundable = 0
```

After the deadline, an excess refund is bounded by:

```text
excess_refundable = F - R - A
```

After such a refund, all existing invariants must still hold.

A final refund is permitted only when:

```text
outstanding == 0
unresolved_economic_operations == 0
```

It refunds the remaining vault balance and produces:

```text
V_after = 0
F = V_after + S + R_after
status = closed
```

## Ambiguous operations

Any unresolved money-moving state blocks refund and finalization:

```text
submitted
confirming
reconciling
needs_recovery
needs_review
disputed
```

States proven to have had no external effect may stop blocking:

```text
rejected_before_submission
failed_before_submission
explicitly_cancelled_before_authorization
```

`completed` requires a new reconciled Channel snapshot containing the resulting
`S` and `V`. The offline runtime does not infer freshness from a technical
receipt.

## Technical and economic results

Refund intent, projection, technical execution, observation, and economic
completion are separate:

```text
RefundRequest
→ RefundProjection
→ RefundExecutionCommitment
→ TechnicalRefundReceipt
→ ChannelRefundObservation
→ ReconciledChannelRefund
```

A transaction signature or technical receipt does not update `R`.
`ReconciledChannelRefund` requires an independently verified observation that
matches the exact expected accounting effect.

## Epoch eligibility

Protocol v1 may determine only:

```text
epoch_transition_eligible
```

Eligibility requires:

```text
previous.status == closed
previous.V == 0
previous.outstanding == 0
unresolved_economic_operations == 0
next_epoch == previous.epoch + 1
```

The eligibility record binds the final closure hash. A prospective next epoch
starts with zero accounting, zero sequence, and the zero voucher hash.

The runtime does not claim that ChannelVault reuses an account, creates a new
PDA, or has executed an epoch transition.

## Consequences

- Activated rights cannot be revoked through time-based refund.
- `A` remains monotonic within an epoch.
- Refund logic uses the final freeze snapshot, not the close-request snapshot.
- Closing preserves valid voucher presentation until the exclusive deadline.
- Ambiguous economic operations fail closed.
- Cross-epoch artifacts remain invalid through epoch-bound domain separation.

## Deferred alternative

A future version may define:

```text
E = cumulative activated rights formally extinguished
outstanding = A - S - E
effective_activated = A - E
effective_activated <= F - R
```

That change requires a new protocol version and coordinated review of Channel
accounting, settlement, closure, receipts, schemas, vectors, and ChannelVault.
It is outside FC-PROTO-005.
