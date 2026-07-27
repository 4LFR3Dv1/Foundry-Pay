# FC-ADR-009: Evidence maturity and deployment authorization

- Status: accepted upon merge
- Date: 2026-07-27
- Work item: `FC-GOV-001`
- Baseline: `8975a4b3edfae070919d68afe851652eb1f71ea8`

## Context

Earlier Channels gates used independent review as a prerequisite for merging
some offline reference artifacts. This made an externally scheduled activity
part of the experimental engineering critical path and conflated four
different statements:

```text
implemented
self-validated
externally reviewed
authorized for deployment or value
```

The distinction became concrete in FC-PROTO-007. Three independent language
implementations and CI evidence can establish reproducible self-conformance,
but they cannot establish an external review or authorize value-bearing use.

Changing the PR gate silently would erase a recorded decision. The policy must
change first, generally and prospectively.

## Decision

Foundry Channels keeps `done` as the work-item execution state and introduces
independent, version-bound records for:

- implementation;
- self-validation;
- external review;
- deployment authorization.

Offline, fake, local-validator, and fixture-only devnet artifacts may advance
without external review when their limitations and authorizations are explicit.
Mainnet and real-value authorization require passed external review of the exact
applicable artifacts.

FC-CTRL-014's review-before-merge rule is superseded only after this ADR is
merged. No external review is inferred. PR #34 must then rebase, update its
contract and evidence, and rerun all gates.

## Consequences

- `done` remains useful and does not mean audited.
- A review can be `passed` historically and `stale` for current code.
- Authorization becomes an operational decision, not the final rung of a
  maturity ladder.
- Experimental devnet work can progress while mainnet and real value remain
  blocked.
- Every public claim can name the exact evidence and authorization supporting
  it.
- Previously reviewed artifacts retain their historical review records.
- The policy does not weaken normal repository review requirements for
  security- or money-moving changes.

## Rejected alternatives

### Merge PR #34 before changing governance

Rejected because it would violate its frozen coordination contract.

### Treat `self_validated` as the only component status

Rejected because it loses work-item state, review history, artifact staleness,
and environment-specific authorization.

### Require external review for all experimental merges

Rejected because it makes external availability the critical path without
adding proportional safety to offline and fixture-only work.

### Allow mainnet based on self-validation

Rejected because self-validation does not provide independent assurance for
real-value execution.
