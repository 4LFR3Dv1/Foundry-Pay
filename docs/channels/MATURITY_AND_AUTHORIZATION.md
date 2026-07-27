# Evidence maturity and deployment authorization

This policy separates delivery, validation, review, and operational authority.
It applies program-wide to Foundry Channels artifacts and supersedes any rule
that treats merge, `done`, or green CI as an external security review.

## Independent dimensions

`work_item_status` describes execution of a bounded work contract:

```text
blocked → ready → active → review → done
```

It does not describe audit or deployment safety.

Every material artifact separately records:

```text
implementation
self-validation
external review
deployment authorization
```

The records are version-bound. A review of commit A remains historical evidence
but does not review commit B. An authorization for one Program ID, IDL, cluster,
mint, or economic limit does not authorize another.

## Maturity records

### Implementation

Allowed states:

```text
not_started
in_progress
complete
```

`complete` identifies the immutable commit that satisfies the implementation
contract.

### Self-validation

Allowed states:

```text
not_performed
pending
passed
failed
stale
```

`passed` requires an exact validated commit and an evidence reference.
`stale` means the recorded validation applies to an older artifact.

Self-validation may support merge and experimental work. It is not an external
review, audit, production approval, or real-value authorization.

### External review

Allowed states:

```text
not_required
not_performed
pending
passed
failed
stale
```

`passed` requires:

- exact reviewed commit;
- reviewer identity;
- immutable report or formal review reference;
- completion timestamp.

Any material change after the reviewed commit makes the review `stale` for the
current artifact until scope-aware review confirms otherwise.

## Deployment authorization

Each environment is decided independently:

```text
local_validator
devnet_fixture
mainnet
real_value
```

Authorization states are:

```text
blocked
allowed
suspended
revoked
expired
```

`allowed` requires an exact artifact commit, a decision reference, scope, and
constraints. Where applicable, constraints bind:

- release;
- cluster and genesis hash;
- Program ID;
- IDL SHA-256;
- mint;
- upgrade authority;
- economic limit;
- validity window.

An authorization cannot be broadened by inference. Missing scope is denied.

## Minimum gates

| Activity | Minimum evidence | External review |
|---|---|---|
| offline reference runtime | implementation complete and self-validation passed | not required before merge |
| fake adapter or consumer fixture | self-validation, explicit fixture boundary, no real assets | not required before experimentation |
| local validator | self-validation, threat model, invariant tests | not required before experimentation |
| fixture-only devnet | explicit authorization, public limitations, Program ID and evidence | may remain not performed |
| mainnet deployment | passed exact-version protocol and program review | required |
| real-value execution | passed exact-version review and explicit economic authorization | required |

Normal repository ownership and non-author review rules still apply to
security- or money-moving changes. “External review” here means an explicitly
commissioned independent protocol, cryptographic, or program assessment; it is
not inferred from ordinary code review.

## FC-PROTO-007 transition

The earlier FC-CTRL-014 coordination contract required an independent
conformance review before merge. FC-GOV-001 changes that program-wide policy
before FC-PROTO-007 is integrated:

```text
offline independently implemented conformance
→ may merge after reproducible self-validation
→ external review remains not_performed
→ mainnet and real-value use remain blocked
```

This does not claim that a review happened, waive future exact-version review,
or authorize any deployment. PR #34 must incorporate the merged governance
baseline, update its task/evidence records, and pass its complete CI again.

## Staleness

The following make a review or authorization stale unless explicitly declared
out of scope by the original decision:

- signed preimage or canonicalization change;
- domain, profile, schema, or rejection semantic change;
- instruction, account layout, authority, or IDL change;
- Program ID or upgrade authority change;
- cluster, genesis hash, or mint change;
- dependency change affecting security behavior;
- economic-limit broadening.

Stale evidence remains historical evidence. It cannot authorize the current
artifact.

## Prohibited claims

Without corresponding version-bound evidence and authorization, do not claim:

- externally reviewed;
- audited;
- production-ready;
- safe for real assets;
- mainnet-authorized;
- secure custody;
- exactly-once blockchain execution.
