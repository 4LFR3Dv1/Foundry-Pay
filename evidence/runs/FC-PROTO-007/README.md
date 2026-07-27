# FC-PROTO-007 evidence

This pack records independent Python, TypeScript, and Rust execution against
the frozen FC-PROTO-006 canonicalization registry.

## Result

- eight positive vectors produced identical bytes, byte lengths, and SHA-256
  hashes;
- twenty negative vectors produced identical rejection stages and codes;
- each runner executed in a separate CI job with its pinned runtime;
- the passive comparator consumed only emitted JSONL and frozen expectations;
- poisoning every expected result field left all three runner streams byte-for-
  byte unchanged;
- the comparator rejected the poisoned expectation set;
- the full repository regression passed.

The evidence proves offline protocol conformance. It does not prove Solana
execution, ChannelVault behavior, production readiness, or external security
review.

## Reproduction

Use the pinned toolchains in
`contracts/channel/conformance/toolchains.v1.json`, install the committed lock
files, then run:

```text
python tests/channels/conformance/run_cross_language.py
```

The workflow execution and immutable commits are recorded in
`validation-report.json`.

Under FC-ADR-009, this offline artifact may merge after reproducible
self-validation while external review remains explicitly `not_performed`.
External exact-version review is still required before mainnet or real-value
authorization. This pack authorizes no ChannelVault or deployment.
