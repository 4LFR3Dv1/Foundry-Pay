# FC-ADR-007 — Canonicalization and hash profiles

- Status: accepted
- Date: 2026-07-27
- Work item: FC-PROTO-006
- Baseline: `469a28e9a92a7d443b9e20621ade2e4d23a09eee`

## Context

Channel objects already use RFC 8785 and SHA-256, but validation, projection,
self-hash exclusion, and domain checks are distributed across Voucher,
RecipientBinding, settlement, closure, journals, and the External Execution
Protocol. Equivalent implementations could therefore disagree about the
preimage while each appears locally correct.

## Decision

Protocol v1 freezes this pipeline:

```text
strict wire parsing
→ closed schema/object validation
→ explicit normative projection
→ RFC 8785 JCS
→ exact UTF-8 bytes
→ SHA-256
→ sha256:<64 lowercase hexadecimal characters>
```

Five profiles are normative: signed payload, canonical record, self-hashed
record, journal chain, and raw bytes commitment. Evidence artifact hashes use a
sixth, non-economic profile and namespace.

Signed authority payloads carry an explicit `domain` string. Existing
operational v1 records bind their exact `type` and `protocol_version` in the
preimage; the closed domain registry maps that pair to one exact domain. This
preserves the reviewed v1 preimages. It is not a permissive fallback: an
unregistered type/version pair is rejected, prefix matching is forbidden, and
new operational objects must carry an explicit domain or define a new profile
version.

The common Python primitive validates JSON-domain safety and performs only
canonical byte and digest operations. Object modules retain closed-field,
economic, authority, and lifecycle validation. They must supply an explicit
projection; the primitive never infers fields or serializes dataclasses.

Self-hashed records exclude exactly one declared own-hash field. Signatures are
excluded only where the registry explicitly defines a signed payload envelope.
Raw bytes are hashed directly and are never encoded through JSON first.

## Compatibility

Voucher and RecipientBinding canonical bytes and hashes remain unchanged.
Existing settlement, recovery, closure, refund, finalization, and journal
preimages remain unchanged because their exact `type` and `protocol_version`
were already present. FC-PROTO-006 centralizes the low-level operation and
publishes those preimages; it does not introduce a second v1 interpretation.

Any future security correction that changes a preimage requires a coordinated
pre-runtime migration or a new domain/profile/version. Legacy fallback,
automatic normalization, and dual interpretations under one version are
forbidden.

## Consequences

- FC-PROTO-007 can implement the same rules without importing Python runtime
  code.
- Duplicate wire keys, floats, unsafe integers, lone surrogates, unknown
  domains, malformed hashes, and non-canonical set arrays fail closed.
- Evidence file digests cannot be presented as economic protocol hashes.
- ChannelVault and on-chain verification remain outside this decision.

