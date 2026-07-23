# FP-REC-001 evidence

Implementation commit: `5a57bdaee36ab3c66f8e378811134d3c804a8d8a`

This bundle deterministically backfills the merged FP-E2E-001 devnet proof into
the normative reconciliation protocol:

- `l1-observation.json` is the immutable, normalized L1 source observation;
- `l2-observation.json` is the independently obtained Alchemy observation;
- `reconciliation-result.json` records `finalized`, `l1_verified`, and
  independent verification `l2_verified`;
- `manifest.json` binds the evidence to the implementation commit and
  observation hash.

Both L1 and L2 are live observations of the FP-E2E-001 transaction. L2 was read
directly from Alchemy using `getTransaction` and `getSignatureStatuses`. Alchemy
has a provider, trust domain, endpoint identity, transport invocation, and parser
boundary distinct from the L1 backfill. The credential-bearing endpoint was used
only at runtime and was not persisted.

To reproduce, set a credential-bearing Alchemy devnet endpoint in the current
process, then
invoke `write_fp_rec_001_live_l2_evidence` with implementation commit
`5a57bdaee36ab3c66f8e378811134d3c804a8d8a`. Never place the endpoint in a
tracked file or command transcript.

Then run:

```text
python -m pytest tests/reconciliation -q
```
