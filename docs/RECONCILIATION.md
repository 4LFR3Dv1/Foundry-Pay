# Reconciliation Protocol

FP-REC-001 separates execution from observation. An executor receipt is an input
for locating an operation; it is never accepted as evidence that the economic
effect occurred.

## Status model

The aggregate reports three independent properties:

- `execution_status`: `unknown`, `confirmed`, or `finalized`;
- `reconciliation_status`: `pending`, `l1_verified`, or
  `reconciliation_disputed`;
- `independent_verification`: `pending`, `l2_verified`, `l3_verified`, or
  `disputed`.

`confirmed` and `finalized` describe chain commitment. `l1_verified` describes
the observed balance effect. `l2_verified` and `l3_verified` require a qualifying
independent source. A disagreement preserves execution status and opens
`reconciliation_disputed`; it does not pretend that a confirmed transaction was
reverted.

## Source classes

- **L1 — operational observation:** a direct RPC observation made by the
  Foundry reconciler, independent of the signer and broadcaster process.
- **L2 — independent RPC:** another provider, trust domain, and endpoint
  identity. It uses its own reader/parser and does not consume the executor
  receipt as an observation.
- **L3 — distinct pipeline:** an indexer, explorer, archival RPC, validator, or
  third-party verifier with a materially different observation pipeline.

Source metadata comes from the authoritative `SourceRegistry`. An observation
cannot promote itself to L2 or L3 by changing labels. A candidate is diverse
from L1 only if provider, trust domain, and endpoint identity are all different.
Endpoint identities are normalized and hashed so credentials are never stored.

## Normative observation

Every source produces a closed `source_observation` object conforming to
`reconciliation-observation.v1.schema.json`. The implementation additionally
validates semantic constraints that JSON Schema alone cannot express:

- Solana addresses decode to exactly 32 bytes;
- amounts are unsigned base-unit strings, never floats;
- source and destination deltas are equal to the observed amount;
- `null`, unknown fields, unsafe integers, NaN, and Infinity are rejected;
- timestamps are real UTC calendar timestamps with second precision;
- raw provider responses are hashed as bytes and are not signed domain objects.

The observation hash is SHA-256 over RFC 8785 canonical JSON after domain
normalization. Object property order is immaterial; array order and every
material field remain significant.

## Consensus

The expected settlement is authoritative Foundry data: request, obligation,
network, signature, accounts, and amount. Each observation is compared against
it independently.

1. A matching L1 establishes `l1_verified`.
2. A matching, source-diverse L2 establishes `l2_verified`.
3. A matching, source-diverse L3 establishes `l3_verified`.
4. Any material disagreement establishes `reconciliation_disputed` and
   preserves every observation and disagreement field.
5. An unavailable independent source leaves verification `pending`; it does not
   delay or rewrite the operational execution result.

## FP-E2E-001 backfill

The first live devnet proof is converted into the normative L1 format by
`backfill_fp_e2e_001`. Its stored proof slice is hashed as the raw observation
payload. The resulting bundle proves L1 reconciliation and intentionally records
L2 as `pending_external_provider`.

The live L2 gate requires a devnet endpoint operated by a provider and trust
domain different from the L1 public RPC. Supplying that endpoint completes an
external observation; it does not require a protocol or consensus change.

## Verification

```text
python -m pytest tests/reconciliation -q
python -m ruff check services/reconciliation tests/reconciliation
python -m ruff format --check services/reconciliation tests/reconciliation
```

The tests cover schema validity, deterministic hashing, tampering, diversity,
source-registry authority, L1/L2/L3 transitions, disagreement preservation,
unavailable sources, and adapter hashing.
