# SA-CHAN-000 evidence

This pack proves the offline, transport-independent fixture boundary at
functional commit `7513587c556e7604d8b357c7d149fe30cfb28cef`.

It covers closed capability contracts, deterministic exact-byte preparation,
SQLite idempotency, restart-safe recovery, at-most-one controlled submission,
technical receipts, and independent fixture reconciliation.

The allowed claim is:

> Transport-independent channel capability contracts and an adversarial fake
> adapter proving recovery and consumer-state behavior without Solana or
> economic authority.

Technical confirmation is not economic completion. No Solana SDK, RPC, wallet,
signer, IDL, ChannelVault instruction, devnet deployment, mainnet readiness,
real-value safety, or external review is claimed.

Regenerate from repository root:

```text
python evidence/runs/SA-CHAN-000/generate_evidence.py
```
