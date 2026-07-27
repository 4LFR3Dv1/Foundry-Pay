# FC-SEC-002 contract

FC-SEC-002 is the final offline gate between well-formed channel objects and
correctly contextualized cryptographic authority. It does not implement
ChannelVault, Solana execution, wallets, RPC, Cloud services, or a consumer
product.

## Frozen scope

The implementation has three independent proof classes.

### A. Protocol v1 replay resistance

For every signed authority object, the harness must retain the original
signature and mutate exactly one material dimension into another structurally
valid context. Verification must reject without economic effect or authority
advancement.

The registry must cover every semantically applicable dimension:

```text
object type, protocol version, hash profile, environment, network,
genesis hash, program ID, channel ID, channel account, epoch, sender,
recipient commitment, bound wallet, mint, asset policy, sequence,
and previous voucher hash
```

A schema rejection caused only by making the mutation malformed does not prove
domain separation.

### B. Cross-type and cross-profile collision resistance

Voucher, recipient-binding, settlement, closure, execution-commitment, and
receipt authority cannot be reinterpreted as one another. Reusing a valid
signature under another registered domain or profile must fail with no effect.
Equal business values do not imply equal canonical bytes or hashes across
authority types.

### C. Version lifecycle

Unknown protocol versions and profiles fail closed. A verifier must not remove
new fields, retry an older profile, or interpret an unknown object as v1.

Rotation changes the accepted context for newly issued objects; it never
rewrites an already signed object. Cryptographic rights may become ineligible
only through verifiable protocol lifecycle such as finalization, epoch advance,
monotonic supersession, consumed binding, or expiry before activation. A
Cloud-controlled revocation list is not an authority in v1.

Protocol v1 objects remain v1. Migration means a new epoch or channel until a
future, explicitly authorized on-chain migration contract exists.

## Cross-language decision contract

Where the frozen Python, TypeScript, and Rust conformance runners cover the
object, all three must agree on:

```text
decision
stage
stable rejection code
```

Positive controls must still agree on exact canonical bytes and SHA-256. The
comparator is passive and cannot repair, normalize, or reinterpret a result.

## Evidence and properties

Property-based tests must publish deterministic seeds, example counts,
minimized counterexamples, and library versions. Each accepted baseline and
rejected mutation must record the state before and after verification.

`zero effect` means:

```text
economic effect count = 0
authority advancement count = 0
verified/activation_requested/authorized/completed transitions = 0
```

It does not require an audit journal to remain byte-for-byte unchanged. A
durable `rejected` event is permitted and expected when the runtime is designed
to make invalid attempts observable. Such an audit effect cannot grant
authority, activate a right, authorize execution, or declare economic success.

The required evidence classes are:

```text
threat matrix
domain-dimension registry
mutation cases and language streams
cross-language comparison
semantic-collision report
downgrade report
version-lifecycle report
no-effect report
artifact manifest
```

## Maturity and authorization

FC-SEC-002 may be integrated with implementation complete, self-validation
passed, and external review not performed. That state authorizes only offline
and local-validator experimentation.

Devnet fixtures, mainnet, and real-value use remain blocked. External review of
the exact artifacts is required before mainnet or real-value authorization.

## Stop conditions

Stop rather than weaken the tests if:

- a material dimension is not cryptographically bound;
- two languages reject at different semantic stages or with different codes;
- an unknown version or profile falls back to an older interpretation;
- Cloud state is required to revoke an otherwise valid right;
- a rejected mutation advances verified, activation-requested, authorized, or
  completed state;
- remediation requires silently changing a frozen v1 preimage.

The last condition is a security finding requiring an ADR, an explicit version
decision, regenerated vectors, and full conformance.
