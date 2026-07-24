# Foundry Channels decision register

Status terms are `accepted`, `proposed`, and `superseded`. Accepted decisions
are binding for the MVP unless a later ADR explicitly supersedes them.

| ID | Status | Decision | Consequence | Authority |
|---|---|---|---|---|
| FC-D-001 | accepted | V1 is a funded, unidirectional, single-sender, single-recipient channel | no bilateral netting, routing, or streaming semantics | [ADR-001](ADR/FC-ADR-001-channel-primitive.md) |
| FC-D-002 | accepted | vouchers contain cumulative authorized totals | settlement is `activated total - already settled`, bounded by funding and policy | [ADR-001](ADR/FC-ADR-001-channel-primitive.md) |
| FC-D-003 | accepted | signed vouchers are `issued`; only program-accepted sequences are `activated` and settleable | a relay may sponsor activation but cannot fabricate the sender signature | [VOUCHER_MODEL](VOUCHER_MODEL.md) |
| FC-D-004 | accepted | ChannelVault state is the economic authority | Cloud indexes and assists but never becomes the balance or rights ledger | [ADR-002](ADR/FC-ADR-002-onchain-offchain-state.md) |
| FC-D-005 | accepted | Foundry-Pay public, Solana-Agent public, and commercial Cloud remain independent | integration uses versioned contracts and no kernel is copied | [ADR-003](ADR/FC-ADR-003-public-private-boundary.md) |
| FC-D-006 | accepted | claim URLs carry an opaque locator in the path and claim private material only in the URI fragment | the fragment must never be sent to the resolver; frontend compromise remains a critical residual risk | [ADR-004](ADR/FC-ADR-004-link-and-recipient-binding.md) |
| FC-D-007 | accepted | initial binding needs claim-key and destination-wallet signatures over one payload | possession of a forwarded link alone is insufficient to silently substitute a wallet | [AUTHORITY_MODEL](AUTHORITY_MODEL.md) |
| FC-D-008 | accepted | recipient rebinding is disabled in the MVP | destination changes cannot occur silently; recovery UX is deferred | [ADR-004](ADR/FC-ADR-004-link-and-recipient-binding.md) |
| FC-D-009 | accepted | closure blocks top-up but keeps voucher activation and settlement open until `claim_deadline` | no refund is allowed during the presentation window; only post-deadline unreserved value is refundable | [CHANNEL_PROTOCOL](CHANNEL_PROTOCOL.md) |
| FC-D-010 | accepted | unknown submission outcome permits status/recovery, never blind retransmission or rematerialization | the system offers controlled at-most-one broadcast, not exactly-once blockchain execution | [FAILURE_AND_RECOVERY](FAILURE_AND_RECOVERY.md) |
| FC-D-011 | accepted | the initial public work remains in `docs/channels/` and `contracts/channel/` | Channels can evolve without prematurely restructuring the stable external-execution package | [ADR-005](ADR/FC-ADR-005-repository-topology.md) |
| FC-D-012 | accepted | the first post-foundation PR is an offline Channel/ChannelFunding validator | implementation starts with conservation and schema semantics, not Cloud or program code | [WORK_GRAPH](WORK_GRAPH.md) |

## Decisions intentionally deferred

- exact Borsh/Rust wire representation and cross-language hash vectors;
- exact sequence gaps policy beyond the MVP default of `+1`;
- browser claim-key storage and recovery;
- claim expiry and close grace production values;
- ChannelVault upgrade governance;
- production custody, identity, compliance, and operations.

These appear in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) with explicit owners and
stop conditions. None permits a mainnet, production, audit, custody, scale, or
exactly-once claim.
