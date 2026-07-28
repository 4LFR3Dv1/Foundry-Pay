# FC-SOL-005 — governance and migration contract

## Normative rule

> Governance may change software, but it cannot silently rewrite economic
> rights already created under the protocol.

This work item is an offline governance model. It does not implement a
multisig, timelock, loader instruction, handler, CPI, deployment, or pause
instruction.

## Authority environments

| Environment | Authority model | Authorization |
|---|---|---|
| offline model | fixture authorities | allowed |
| local validator | experimental deploy authority | blocked by this item |
| devnet fixture | public, constrained authority decision required | blocked |
| mainnet | reviewed multisig/timelock or immutability decision | blocked |
| real value | exact-version external review and economic authorization | blocked |

An experimental deploy authority is not production governance. Solana-Agent,
Foundry Cloud, a signer service, or a single operational key cannot become the
unilateral production upgrade authority by inference.

## Governance lifecycle

```text
draft
→ proposed
→ approved
→ timelocked
→ executable
→ executed
→ verified
```

Lateral terminal states are:

```text
rejected
cancelled
expired
verification_failed
```

Approval does not execute an upgrade. Timelock expiry does not prove execution.
Execution does not prove that the installed binary matches the proposal.

Every proposal binds:

- current and proposed binary SHA-256;
- source commit and repository;
- pinned toolchain and lockfile SHA-256;
- Program ID and current ProgramData;
- account-layout hash;
- instruction-registry hash;
- signed-message-registry hash;
- compatibility class;
- earliest execution time;
- authority set, threshold, and approvals;
- post-execution verification result.

## Compatibility classes

### Compatible under the same Program ID

- internal bug fix preserving all normative bytes and authority;
- compute optimization preserving effects and errors;
- non-normative human-readable messages;
- supplemental observability that grants no authority.

Compatible changes still require the declared process and exact artifact
verification.

### Versioned

- new instruction or account field;
- changed preimage, domain, profile, authority, lifecycle, or temporal bound;
- changed account encoding or meaning;
- changed recipient-binding or settlement semantics.

A versioned semantic change requires a new protocol/account version and,
unless an independently reviewed migration says otherwise, a new Program ID.

### Forbidden over existing v1 rights

- reinterpret reserved v1 bytes;
- reduce `activated_authorized_total`;
- redirect an outstanding right;
- merge outstanding right with sender-controlled unallocated capacity;
- permit unilateral recipient rebind;
- refund reserved activated capacity;
- make settlement depend on a new third-party authority;
- rewrite signed v1 objects as another version.

## Emergency controls

Emergency controls follow:

```text
pause ingress
preserve exits
preserve activated rights
```

A pause may block:

- new channel initialization;
- new funding;
- new voucher activation.

A pause cannot indefinitely block:

- settlement of an already activated right;
- eligible refund of unallocated capacity;
- safe finalization after all rights and capacity are resolved.

An emergency path cannot transfer value to governance, substitute the
recipient, reduce activated totals, or bypass evidence requirements.

## Migration

Protocol v1 objects remain v1. They are not rewritten in transit.

For an active channel, migration must preserve independently:

```text
unallocated_capacity = funded - refunded - activated
outstanding_right = activated - settled
settled_total
refunded_total
latest_activated_sequence
latest_activated_voucher_hash
recipient binding
mint and epoch
```

The conservative default is no automatic active-channel migration:

```text
old program preserves settlement/refund/finalization exits
new channels use the new program/version
```

Migration eligibility is not migration execution.

## Program ID policy

Same-Program-ID upgrades are restricted to compatible changes whose manifest
proves unchanged normative registries and account meaning. Semantic changes
use a new version and normally a new Program ID. Keeping the same Program ID
for a semantic change requires a later, independent authorization and cannot be
inferred from this work item.

## Operation identity precondition

Before handlers, `SA-CHAN-002`, `SA-CHAN-003`, or real execution preparation,
durable operation identity must bind:

```text
operation_id
→ canonical operation commitment hash
```

The required behavior is:

```text
same operation_id + same commitment
→ replay/idempotent result

same operation_id + different commitment
→ OPERATION_CONFLICT
```

The commitment must cover instruction kind and bytes, Channel PDA, material
account metas, protocol/version, and the operation ID. FC-SEC-004 proves
at-most-one modeled effect; it does not claim this stronger conflict
classification.

## Explicitly unproven

- loader or ProgramData behavior;
- real multisig or timelock execution;
- reproducible deployed binary;
- pause or migration handlers;
- local-validator, devnet, or mainnet deployment;
- external review or production safety.
