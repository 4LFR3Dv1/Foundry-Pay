# Future Solana-Agent channel capabilities

These descriptors are planning inputs. `FOUNDATIONS-001` does not implement
them and does not change Solana-Agent authority.

## Capability set

Required by the mission:

```text
solana.channel.open.v1
solana.channel.top_up.v1
solana.channel.inspect.v1
solana.channel.settle.v1
solana.channel.close.v1
solana.channel.refund.v1
```

Required by the accepted activation/binding architecture:

```text
solana.channel.activate_voucher.v1
solana.channel.bind_recipient.v1
```

Optional only after MVP decision:

```text
solana.channel.rebind_recipient.v1
```

## Generic capability descriptor

Each advertised capability must include:

```text
capability_id
capability_version
network
genesis_hash
program_id
program_version
idl_hash
supported_token_programs
supported_account_versions
supported_instruction_versions
max_fee_lamports
simulation_support
status_support
recovery_support
evidence_support
```

Capability discovery is descriptive, not permission. Foundry global policy,
Solana-Agent local policy, exact execution authorization, and signer checks
still apply.

## Input authority

Solana-Agent receives a closed economic plan containing exact:

- channel and operation identifiers;
- program, channel account, mint, and participant accounts;
- amount and expected pre/post totals;
- voucher/binding hashes and sequences;
- lifecycle and expiry expectations;
- allowed programs and maximum fee.

It may derive deterministic PDAs/ATAs and choose safe transaction mechanics
inside constraints. It may not choose or change the economic amount, mint,
recipient, channel, voucher, or close/refund right.

## Expected output

Preparation returns:

- exact serialized message;
- prepared message hash;
- normalized simulation attestation;
- observed program/account/version facts;
- execution commitment;
- local policy decision and evidence requirements;
- preparation expiry.

Execution returns technical status/receipt only. Foundry independently
reconciles Channel account fields and vault/recipient token deltas.

## Reuse

Reuse without kernel modification:

- JSONL envelope and durable gateway request idempotency;
- `prepare`, `authorize-and-execute`, `status`, `recover`, `evidence`;
- signature-first execution journal;
- exact-message signer checks;
- devnet/RPC safety and secret redaction;
- technical receipt and chaos recovery behavior.

Extensions:

- capability discovery command or versioned capability response;
- ChannelVault instruction builders and account decoders;
- channel-specific local policy rules and allowed programs;
- evidence extraction for channel fields and token deltas.

Not added:

- voucher issuance;
- link resolution;
- user identity;
- channel business state machine;
- final reconciliation authority.
