# FC-PROTO-005 evidence

This pack records the offline reference implementation of Foundry Channels v1
close, expiry, refund, finalization, and epoch-eligibility semantics.

## Proven statements

- Voucher expiry can prevent future activation but does not extinguish an
  already activated right.
- Closure uses distinct request and freeze snapshots.
- Activation eligibility uses the exclusive rule `now < claim_deadline`.
- Refund projection uses final activated total and preserves
  `F = V + S + R` and `0 <= S <= A <= F - R`.
- Every unresolved money-moving state blocks refund and finalization.
- SQLite constraints and `BEGIN IMMEDIATE` serialize refund reservations.
- Reservations are scoped to the closure rather than to a caller-controlled
  freeze hash, and reconciled refunds establish a refunded-total high-water.
- A controlled refund has at most one persisted submit intent.
- An exact execution commitment is durably persisted before submit.
- A technical receipt is not economic completion.
- An `unknown` technical result cannot be overwritten by a later receipt.
- An independently verified matching observation is required for completion.
- Epoch output is eligibility only; it does not claim an executed transition.

## Boundaries

The runtime is offline. It does not use RPC, a wallet, a signer, Solana SDK, or
ChannelVault. Caller-supplied snapshots and observations are validated but are
not represented as on-chain facts.

Canonical settlement objects remain draft until FC-PROTO-006.

## Reproduction

```text
python -m pytest
python -m ruff format --check .
python -m ruff check .
python scripts/check_secrets.py
python scripts/check_channel_foundation.py
npm test --prefix packages/external-execution-protocol/typescript
npm test --prefix packages/channel-protocol/typescript
```

The first independent review of head `35148a91...` returned `REQUEST_CHANGES`.
The eight findings are recorded in `independent-review-35148a9.json` and were
remediated in `8420ee25...`. The re-review of `1c7f402...` closed seven of
those findings and found two additional accounting-transition blockers,
recorded in `independent-review-1c7f402.json`. They were remediated in
`286eb823...`. The final independent re-review approved exact head
`5e0737ae...`; the decision is recorded in
`independent-rereview-5e0737a.json`.
