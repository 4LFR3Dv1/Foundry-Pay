# Foundry Channel Protocol — Python reference

This package provides deterministic, offline reference validation for channel,
funding, voucher, recipient-binding, and settlement objects. It validates
caller-provided snapshots and derives:

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

## Offline settlement runtime

`SettlementRuntime` persists the economic request, exact prepared-execution
commitment, authorization, single submit intent, technical receipt, recovery
observations, and final reconciled receipt in SQLite.

The runtime deliberately separates:

```text
technical executor acceptance
!= independent economic observation
!= reconciled completion
```

An unknown technical result enters `needs_recovery`. Repeated recovery never
submits again. Recovery accepts status only from the executor bound by the
execution commitment, validates the closed response contract, and persists the
exact response hash. Ambiguous `needs_review` and `disputed` records continue
to reserve their economic amount.

A reconciled receipt is created only when every observation passes an injected
source-specific verifier and the supplied channel, epoch, mint, destination,
settled-total delta, vault delta, and recipient delta all match. `source_id` is
never accepted as self-authenticating evidence.

This is a controlled offline model. It does not provide RPC, wallet, signer,
ChannelVault, Cloud, custody, consumer, or exactly-once blockchain behavior.
