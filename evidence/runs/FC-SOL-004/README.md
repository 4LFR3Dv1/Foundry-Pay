# FC-SOL-004 evidence

This pack proves the pure ChannelVault transition model against deterministic,
property-based, and bounded sequence tests.

Reproduce from the repository root:

```text
python evidence/runs/FC-SOL-004/generate_evidence.py \
  --baseline 399d9706702a04ea399d5e35fb4f4fae31c20180 \
  --implementation-commit da8baf5f008653f771c589adfa79f82503e1e2b4
```

The allowed claim is:

> Bounded transition exploration and property-based validation found no
> violation within the published model and bounds.

The pack is not formal verification and does not prove a Solana handler,
runtime CPI atomicity, token transfers, local-validator execution, deployment,
mainnet safety, or real-value use. External review is `not_performed`.
