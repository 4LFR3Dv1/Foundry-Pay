# Foundry Channel Protocol — Python reference

This package provides deterministic, offline validation for `Channel` and
`ChannelFunding` v1 objects. It validates caller-provided snapshots and derives:

```text
F = V + S + R
0 <= S <= A <= F - R
outstanding_right = A - S
unallocated_capacity = F - R - A
```

It performs no RPC, wallet, signing, Cloud, or program operation. A successful
validation does not prove that a snapshot was observed on-chain.

```python
from foundry_channel_protocol import validate_channel

projection = validate_channel(channel)
assert projection.vault_balance_base_units == 60_000_000
```
