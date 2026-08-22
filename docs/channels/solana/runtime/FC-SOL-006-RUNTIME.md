# FC-SOL-006 — executable ChannelVault runtime

Status: positive local lifecycle passed; certification gates remain
Current evidence class: observed local-validator lifecycle
Local-validator evidence: positive lifecycle passed, negative matrix pending
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

## Positive local-validator lifecycle

All eight ChannelVault operations were observed in one complete local-validator
lifecycle under Agave `v2.1.21`: initialization, funding, voucher activation,
recipient binding, settlement, close request, snapshot-backed restart/warp,
refund, final settlement, and finalization. The validator produced a full
snapshot at or after the finalized close checkpoint before restart; all required
accounts and `ChannelState=Closing` persisted across the restart.

The terminal observed conservation was:

```text
funded     100000000
activated   60000000
settled     60000000
refunded    40000000
vault               0
recipient    60000000
```

The negative validator matrix is now locally certified as a separate
fail-closed gate: 18/18 rejection cases matched the expected error registry
code and preserved the economic state. No devnet or real-value execution is
implied.

The complete per-case receipt is preserved in
`evidence/runs/FC-SOL-006/negative-local-validator-run.jsonl`.

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

The historical receipt above proves host compilation and deterministic
handler/state tests. The current local lifecycle evidence proves positive
validator execution, but does **not** yet prove:

- the frozen negative account/meta/signature matrix under validator execution;
- a trusted/deployed Program ID;
- Solana devnet deployment;
- mainnet or real-value readiness.

The positive lifecycle artifact and run details are recorded in
`evidence/runs/FC-SOL-006/validator-transport-observation.md`.
