# FP-FAIL-002 evidence

Foundry implementation:
`951ab699c827e7e7dbfca59a3beb6ebca4800935`

Pinned Solana-Agent implementation:
`5707240af22bc288149b68456b2a9fe810928efb`

This directory contains nine generated scenario reports. Eight launch the
Solana-Agent JSONL gateway, the persistent RPC fault proxy, and the persistent
upstream as separate operating-system processes. The ninth preserves the
Foundry reconciliation history from temporary L2 unavailability through later
L2 convergence.

`manifest.json` confirms:

- nine total scenarios;
- eight real gateway-process scenarios;
- every proxy `sendTransaction` count is at most one;
- the journal checkpoint hash.

`journal-root.json` binds the two implementation commits and the ordered
SHA-256 hashes of all scenario reports. CI uploads this checkpoint under an
artifact name containing the GitHub workflow commit SHA.

`master-demo.json` is the canonical proof:

```text
upstream acceptance
→ persisted proxy response
→ zero client responses delivered
→ gateway needs_recovery
→ restart
→ recovered_confirmed
→ one sendTransaction
→ zero rebroadcasts
```

All signing keys used by the deterministic process matrix are ephemeral and
memory-only. Reports retain SHA-256 references to high-entropy public wire
values rather than embedding raw public keys, signatures, or transaction bytes.
The upstream in this matrix is a persistent local JSON-RPC emulator. Live
devnet execution and two-provider observation remain separately evidenced by
FP-E2E-001 and FP-REC-001.

Reproduce with both repositories checked out as siblings:

```text
python -m pytest tests/chaos -q
```
