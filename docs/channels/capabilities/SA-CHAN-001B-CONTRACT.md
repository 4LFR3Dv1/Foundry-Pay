# SA-CHAN-001B — fixture-only preparation contract

## Decision

`SA-CHAN-001A` remains a valid descriptive-only v1 gate. Its
`foundry.channels.operation.v1` and `program_profile = not_deployed` preimages
are immutable and can never be promoted to preparation or execution authority.

Before `SA-CHAN-002` or `SA-CHAN-003`, Solana-Agent must publish a separate
profile:

```text
domain: foundry.channels.operation.v2
program_profile: fixture_unexecuted
preparation: offline only
execution_supported: false
deployment_authorized: false
```

The fixture profile binds a fixed fixture Program ID, network and genesis
identity, Channel PDA, exact instruction bytes, ordered account identities,
signer/writable flags, authority profile, and the frozen descriptor registry
hashes. It does not claim that the Program ID is deployed.

## Funding identity

Funding v2 is:

```json
{
  "amount": "100000000",
  "funding_request_hash": "sha256:<64 lowercase hex>"
}
```

`amount` is not identity. Timestamp is not identity.

```text
same funding_request_hash + another operation_id
→ OPERATION_ALIAS_CONFLICT

same amount + different funding_request_hash
→ distinct legitimate funding operations
```

## Identity chain

```text
operation_id
→ durable operation_commitment
→ preparation_id
→ instruction_commitment
→ optional future transaction_commitment
→ future exact-byte authorization
```

A preparation must re-read and verify the durable operation reservation. An
in-memory object alone is insufficient.

`instruction_commitment` binds exact instruction bytes and ordered account
metas. `transaction_commitment` remains absent until a complete Solana message
with fee payer and recent blockhash exists.

## Capability support

The contract publishes a closed per-capability matrix:

```text
channel.initialize          offline_preparation
channel.fund                offline_preparation
channel.activate            offline_preparation
channel.bind_recipient      descriptive_only
channel.settle              offline_preparation
channel.request_close       descriptive_only
channel.refund_unallocated  descriptive_only
channel.finalize_close      descriptive_only
```

This matrix describes the target after `SA-CHAN-002` and `SA-CHAN-003`.
`SA-CHAN-001B` itself only freezes the common representation and still reports
every functional preparation capability as not implemented.

`SA-CHAN-003A` owns binding, close, refund, and finalization preparation.

## Common paths

`SA-CHAN-001B` exclusively owns:

```text
gateway/channel_preparation_common.py
contracts/capabilities/foundry-channel-vault/channel-preparation-common.v1.schema.json
contracts/capabilities/foundry-channel-vault/channel-operation.v2.schema.json
```

After integration, `SA-CHAN-002` and `SA-CHAN-003` consume these files as
read-only inputs.

Neither functional branch may modify:

```text
gateway/channel_operation.py
gateway/channel_discovery.py
```

## Boundaries

This gate introduces no RPC, signer, wallet, transaction, handler, CPI, token
transfer, local-validator execution, deployment, devnet, mainnet, or
real-value authorization.
