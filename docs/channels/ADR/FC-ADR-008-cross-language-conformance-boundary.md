# FC-ADR-008: Independent cross-language conformance boundary

- Status: accepted for implementation
- Date: 2026-07-27
- Work item: `FC-CTRL-014`
- Applies to: `FC-PROTO-007`
- Baseline:
  `17b656cbdd6ae53cece9cebb9123058c03e67b82`

## Context

FC-PROTO-006 froze normative projections, RFC 8785 bytes, SHA-256 hashes,
domains, profiles, and positive and negative vectors. A Python implementation
already exercises those contracts, but one implementation cannot establish
that the protocol is independently implementable.

The positive vector files contain expected bytes and hashes. A runner that
echoes those fields could appear conformant without implementing the protocol.
Likewise, reporting only `rejected` would conceal incompatible parsing,
validation, domain, and hash behavior.

## Decision

FC-PROTO-007 uses three operationally independent runners:

```text
Python runner
TypeScript runner
Rust runner
       |
       +-- each reads the same frozen source inputs
       +-- each parses, projects, canonicalizes, hashes, and rejects locally
       +-- each emits the same closed JSONL result contract
                         |
                         v
                  passive comparator
```

For positive vectors, conformance means:

```text
decision = accept
stage = complete
code = ok
canonical bytes identical
byte length identical
SHA-256 identical
```

For negative vectors, conformance means:

```text
decision = reject
stage identical to the vector
code identical to the vector
```

The comparator cannot canonicalize, hash, normalize, repair, infer, or retry.
It validates closed runner outputs and compares them with the frozen vector
expectations.

## Independence rules

Each runner:

- may read the normative manifest, registries, schemas, and vectors;
- must compute JSON-profile results from `source_json`;
- must compute raw profiles from `source_bytes_hex`;
- must not read `canonical_utf8_hex`, `canonical_utf8_base64`, `byte_length`,
  or `expected_sha256` as computation inputs;
- must not import, invoke, generate, embed, or read another runner;
- must not consume another runner's result stream;
- must implement strict parsing, projection, and rejection mapping within its
  own language boundary;
- may use only its pinned language-specific RFC 8785 dependency.

Shared executable conformance logic is prohibited. Shared data contracts are
required.

## Poisoning proof

The functional suite must replace expected positive bytes, lengths, and hashes
with incorrect values while leaving source inputs unchanged. Every runner must
produce exactly the same computed result as before poisoning. The comparator
must then reject the poisoned expectation.

This proves that runners compute instead of echo.

## Consequences

- Three green unit suites are insufficient without the cross-language
  comparator.
- A negative-vector mismatch is a protocol incompatibility even when all three
  runners reject.
- New vectors must define an exact rejection stage and code.
- Dependency lockfiles and toolchains become evidence inputs.
- FC-PROTO-007 does not prove ChannelVault, Solana execution, signatures,
  product demand, mainnet, or production readiness.
