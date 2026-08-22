# FC-SOL-006 evidence

Status: **positive lifecycle and negative local-validator certification passed — remote/deployment gates remain**

This directory records the evidence lineage for the operational ChannelVault
work item. The positive local-validator lifecycle is observed end to end. The
negative validator matrix is now also certified locally as fail-closed; this
does not certify devnet or real-value execution.

## Positive local-validator gate

All eight operations were observed in one complete lifecycle under validator
Agave `v2.1.21`, built with Agave `v3.1.5` and platform-tools `v1.52`.

The lifecycle included a finalized `request_close`, full-snapshot boundary,
restart with `WARP_SLOT = fullSnapshotSlot + 100000`, repeated finalized account
and `ChannelState=Closing` checks, refund, final settlement, and finalization.

Terminal conservation:

```text
funded     100000000
activated   60000000
settled     60000000
refunded    40000000
vault               0
recipient    60000000
```

See `validator-transport-observation.md` for the exact signature, snapshot
slots, account snapshots, SBF hash, transaction evidence, and receipt.

## Negative local-validator gate

Eighteen independent rejection cases passed under validator Agave `v2.1.21`,
using the same SBF artifact built with Agave `v3.1.5` and platform-tools
`v1.52`. Every case had one simulation, exactly one broadcast, matching
expected/actual rejection code, equal pre/post state hashes, and unchanged
vault, sender-token, and recipient-token balances.

The complete per-case receipt is
[`negative-local-validator-run.jsonl`](negative-local-validator-run.jsonl).

## Historical host slice

Functional head:

`c76f0264ddfaed3c9caeee7876092d4aa9bd2ae2`

Pull request: `#78`

Historical PR CI run: `32497047070`

The historical host/conformance evidence remains preserved and is not
reinterpreted by the local-validator result.

## Preserved frozen material

This evidence does not modify:

- `CHANNEL_STATE_SPACE = 490`;
- ChannelState discriminator/offsets;
- channel PDA seeds;
- FC-PROTO-006 canonical signed payloads;
- v1 instruction serialization;
- the eight operation names/discriminators.

## Evidence classification

```text
host compile/test                 observed
real AccountInfo handlers         observed for 8/8 positive operations
instructions-sysvar integration   observed under validator
Clock integration                 observed under validator
System Program CPI                observed under validator
classic SPL Token CPI             observed under validator
snapshot-backed restart           observed
terminal conservation             observed
negative validator matrix         observed; 18/18 fail-closed
SBF artifact                      locally hashed; remote CI pending
Program ID                        not assigned/authorized
devnet deployment                 not performed
mainnet / real value             not authorized
```

No positive local evidence is deployment authorization. Devnet, mainnet, and
real-value execution remain blocked.
