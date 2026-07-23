# External Execution Protocol

Transport-independent contracts for governed execution agents.

## Normative artifacts

- `schemas/external-execution-agent.v1.schema.json`
- `canonicalization/domain-normalization-profile-v1.md`
- `conformance/vectors/protocol-v1.json`
- `conformance/vectors/negative-v1.json`
- Python reference implementation under `python/`
- TypeScript reference implementation and tests under `typescript/`

The package does not contain Solana-Agent internals, keys, RPC credentials, or
business approval logic.

Both language implementations consume the same positive and negative vectors.
Canonical bytes and SHA-256 values are asserted before either implementation
can pass CI.

Regenerate the positive vector after an approved draft-contract change:

```text
python packages/external-execution-protocol/conformance/generate_vectors.py
```

The generated file is then independently verified by both the Python and
TypeScript conformance suites.
