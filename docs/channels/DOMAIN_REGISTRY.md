# Foundry Channels domain registry v1

Domain lookup is exact. Prefix matching and unregistered aliases are invalid.
The machine-readable authority is
`contracts/channel/canonicalization/domains.v1.json`.

## Explicit signed domains

| Domain | Object | Profile | Schema | Authority |
| --- | --- | --- | --- | --- |
| `foundry.channels.voucher` | ChannelVoucher payload | signed payload | channel-voucher | sender |
| `foundry.channels.recipient-binding` | RecipientBinding payload | signed payload | recipient-binding | claim key + destination wallet |
| `foundry.channels.recipient-binding-journal` | binding journal scope | canonical record | recipient-binding | reference journal |
| `foundry.channels.voucher-ledger-scope` | voucher ledger scope | canonical record | channel-voucher | reference journal |

## Operational domains

For compatibility, these v1 domains are bound by the exact `type` and
`protocol_version` literals already included in the projection.

| Domain | Exact v1 type | Profile | Own hash field |
| --- | --- | --- | --- |
| `foundry.channels.channel-snapshot` | `channel` | canonical record | — |
| `foundry.channels.settlement-request` | `settlement_request` | canonical record | — |
| `foundry.channels.settlement-execution-commitment` | `settlement_execution_commitment` | canonical record | — |
| `foundry.channels.settlement-authorization` | `execution_authorization` | canonical record | — |
| `foundry.channels.settlement-observation` | `settlement_observation` | self-hashed record | `observation_hash` |
| `foundry.channels.reconciled-settlement-receipt` | `reconciled_settlement_receipt` | self-hashed record | `receipt_hash` |
| `foundry.channels.recovery-record` | `settlement_recovery_record` | self-hashed record | `recovery_hash` |
| `foundry.channels.settlement-journal-entry` | `settlement_journal_entry` | journal chain | `event_hash` |
| `foundry.channels.closure-request` | `channel_closure_request` | self-hashed record | `request_hash` |
| `foundry.channels.closure-request-snapshot` | `closure_snapshot_at_request` | self-hashed record | `request_snapshot_hash` |
| `foundry.channels.closure-freeze` | `closure_snapshot_at_freeze` | self-hashed record | `freeze_snapshot_hash` |
| `foundry.channels.refund-request` | `refund_request` | self-hashed record | `request_hash` |
| `foundry.channels.refund-projection` | `refund_projection` | self-hashed record | `projection_hash` |
| `foundry.channels.refund-execution-commitment` | `refund_execution_commitment` | canonical record | — |
| `foundry.channels.technical-refund-receipt` | `technical_refund_receipt` | self-hashed record | `receipt_hash` |
| `foundry.channels.refund-observation` | `channel_refund_observation` | self-hashed record | `observation_hash` |
| `foundry.channels.reconciled-refund` | `reconciled_channel_refund` | self-hashed record | `receipt_hash` |
| `foundry.channels.epoch-transition-eligibility` | `epoch_transition_eligibility` | self-hashed record | `eligibility_hash` |
| `foundry.channels.refund-journal-entry` | `refund_journal_entry` | journal chain | `event_hash` |

External Execution Protocol objects retain their existing
`foundry-pay-domain-v1` profile. Prepared messages and signed transactions use
the raw-bytes profile; their channel meaning is carried by the correlated
settlement or refund commitment.
