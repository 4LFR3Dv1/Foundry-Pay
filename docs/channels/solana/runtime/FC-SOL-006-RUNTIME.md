# FC-SOL-006 — executable ChannelVault runtime

Status: active implementation  
Current evidence class: host-compiled executable slice  
Local-validator evidence: not yet performed  
Devnet deployment: not authorized

## Runtime boundary

`FC-SOL-006` promotes the frozen Foundry Channels account/instruction/transition
contracts into a real Solana program crate without changing the 490-byte
`ChannelState`, PDA seeds, FC-PROTO-006 signed bytes, or the eight-operation
registry.

The executable crate is:

```text
programs/foundry-channel-vault/program
```

It is a `cdylib` + `lib` and exposes a Solana `entrypoint!(process_instruction)`.
No `declare_id!` or deploy-time Program ID exists in this slice.

## Implemented handlers

### `activate_voucher`

Accounts are exactly:

```text
channel              writable ChannelState PDA
instructions_sysvar  Solana instructions sysvar
```

The handler:

1. validates the program-owned 490-byte ChannelState and exact PDA;
2. requires the native Ed25519 instruction immediately before ChannelVault;
3. extracts the exact sender-signed FC-PROTO-006 message from the frozen
   self-contained Ed25519 layout;
4. applies the strict FC-SOL-003B runtime authority boundary;
5. applies the FC-SOL-004 transition model at `Clock::unix_timestamp`;
6. writes only the resulting activated total, sequence, voucher hash and
   voucher-expiry fields;
7. emits the success log only after serialization succeeds.

Sequence, cumulative authority and expiry are not trusted from separate runtime
arguments.

### `bind_recipient`

Accounts are exactly:

```text
channel              writable ChannelState PDA
instructions_sysvar  Solana instructions sysvar
```

The handler consumes the frozen two-signature Ed25519 layout, derives the
candidate destination from that layout, verifies the exact FC-PROTO-006 binding
against current ChannelState, applies the transition model and persists only the
verified destination/bound flag.

The initial binding remains one-use. The fixed binding-nonce bytes are not
silently rewritten to create a rebind protocol.

### `request_close`

Accounts are exactly:

```text
channel  writable ChannelState PDA
sender   exact ChannelState.sender transaction signer
```

The handler requires the sender signature, applies the frozen bounded claim
window through the transition model and persists `Closing`, request time and
claim deadline.

## Operations still fail closed

The entrypoint decodes the complete v2 eight-operation registry, but these five
operations deliberately return `InvalidInstructionData` until their runtime
contracts enter the executable slice:

- `initialize_channel`;
- `fund_channel`;
- `settle`;
- `refund_unallocated`;
- `finalize_close`.

No System Program or SPL Token CPI is present yet. This prevents a partial CPI
implementation from being mistaken for an operational payment path.

## Validation receipt — first slice

Functional head:

```text
c76f0264ddfaed3c9caeee7876092d4aa9bd2ae2
```

GitHub Actions PR run:

```text
32497047070
```

Observed result:

```text
protocol                         success
conformance-python               success
conformance-typescript           success
conformance-rust                 success
conformance-poisoning            success
conformance-compare              success
pytest                           578 passed
secret guard                     650 files scanned, passed
```

The pytest suite invokes:

```text
cargo test --manifest-path programs/foundry-channel-vault/program/Cargo.toml
```

and fails the repository CI if the executable crate or its host-side mutation
suite does not compile/pass.

## What this evidence does not prove

This receipt proves host compilation and deterministic handler/state tests for
the first executable slice. It does **not** prove:

- SBF/BPF reproducible artifact production;
- execution under `solana-test-validator`;
- native Ed25519 transaction execution under a validator;
- System/SPL CPI correctness;
- all eight positive operations;
- the frozen negative account/meta/signature matrix under validator execution;
- a Program ID;
- Solana devnet deployment;
- mainnet or real-value readiness.

Those remain gates of the active FC-SOL-006 work item.
