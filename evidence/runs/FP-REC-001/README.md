# FP-REC-001 evidence

Implementation commit: `aba57d0892a27f6b55905995369b652e6f6a8a40`

This bundle deterministically backfills the merged FP-E2E-001 devnet proof into
the normative reconciliation protocol:

- `l1-observation.json` is the immutable, normalized L1 source observation;
- `reconciliation-result.json` records `confirmed`, `l1_verified`, and
  independent verification `pending`;
- `manifest.json` binds the evidence to the implementation commit and
  observation hash.

The L1 observation is live evidence. The conformance suite proves L2/L3
qualification and disagreement behavior using controlled readers, but those
tests are not represented as live independent verification.

Live L2 remains `pending_external_provider`. It requires a Solana devnet endpoint
whose provider, trust domain, and endpoint identity differ from the L1 public
RPC. No L2 claim is made by this bundle.

Reproduce from the repository root:

```text
python -c "from pathlib import Path; from services.reconciliation.backfill import write_fp_rec_001_evidence; root=Path.cwd(); write_fp_rec_001_evidence(root/'evidence/runs/FP-E2E-001/live-proof.json', root/'evidence/runs/FP-REC-001', implementation_commit='aba57d0892a27f6b55905995369b652e6f6a8a40')"
python -m pytest tests/reconciliation -q
```
