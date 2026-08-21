# FC-SOL-003B — runtime preimage and initialization correction

Status: coordination contract  
Authority: local-validator runtime preparation only  
Account layout change: none  
FC-PROTO-006 signed-preimage change: none

## Why this gate exists

`FC-SOL-003` froze a transport-neutral v1 instruction contract before a real
ChannelVault handler existed. `FC-SOL-006` is the first gate that attempts to
execute those contracts against real Solana accounts and the native Ed25519
precompile.

That implementation attempt exposed an operability gap that must be resolved
before an economic handler is written.

The v1 `activate_voucher` instruction carries:

```text
sequence
cumulative_authorized
voucher_hash
voucher_expiry
```

but the exact FC-PROTO-006 sender-signed payload also contains:

```text
domain
protocol_version
environment
network
genesis_hash
program_id
channel_id
channel_account
epoch
previous_activated_voucher_hash
sender
recipient_claim_pubkey
mint
issued_at
expires_at
```

Likewise the v1 `bind_recipient` instruction carries a fixed 32-byte
`binding_nonce`, destination wallet, and binding hash, while the exact
FC-PROTO-006 signed binding payload contains an integer `binding_nonce`, claim
identifier, exact voucher hash, issued/expiry timestamps, and the complete
channel authority domain.

Finally, v1 `initialize_channel` does not carry the immutable
`genesis_hash`/`channel_id_hash` values required by `ChannelState` to validate
those later signed objects.

A runtime that simply verifies an Ed25519 signature over some message and then
trusts independently supplied `sequence`, `cumulative_authorized`, or
destination fields would break the authority model: the economic transition
would not be cryptographically bound to the exact signed statement.

This gate exists to prohibit that shortcut.

## Preserved invariants

The correction MUST NOT change:

- the 490-byte `ChannelState` account layout;
- account discriminator or field offsets;
- PDA seeds;
- classic SPL Token vault derivation;
- the eight-operation ChannelVault registry;
- FC-PROTO-006 canonical signed payload bytes or hashes;
- the FC-SOL-003 Ed25519 precompile layout (immediately preceding,
  self-contained `u16::MAX` references);
- the historical v1 instruction vectors or their evidence.

The old v1 transport profile remains reproducible historical evidence. It is
not silently rewritten.

## Runtime instruction profile v2

Introduce a second instruction serialization profile identified by contract
version `2`. The eight operation names and discriminators remain unchanged; the
version in the instruction header selects the payload profile.

### Initialize v2

`initialize_channel` v2 adds only the immutable information needed to populate
and later validate the frozen account:

```text
channel_nonce: [u8; 32]
genesis_hash: [u8; 32]
channel_id_hash: [u8; 32]
recipient_claim_pubkey: Pubkey
decimals: u8
environment: u8
policy_flags: u32
channel_expiry: i64
```

Rules:

- `environment` must be a known account-model environment code; the public beta
  accepts the devnet profile;
- `policy_flags` must contain only account-model-known bits;
- `channel_id_hash = SHA-256(UTF-8 channel_id)` for every signed payload later
  presented to the program;
- `latest_activated_sequence` begins at `0`;
- `latest_activated_voucher_hash` begins as 32 zero bytes, matching the
  protocol genesis voucher hash;
- the initial one-use recipient binding nonce is protocol integer `1` encoded
  in the existing fixed 32-byte account slot as little-endian `u64` followed by
  24 zero bytes;
- no semantic use is assigned to the reserved 64 account bytes.

### Signed-message consumption

`activate_voucher` and `bind_recipient` do not invent a compact replacement
signature profile.

The runtime consumes the exact signed message bytes already present in the
immediately preceding native Ed25519 instruction. The instruction-contract
crate may expose extraction helpers, but the Ed25519 byte layout remains
unchanged.

For each accepted signed object the runtime must prove all of the following
before state mutation:

1. native Ed25519 program ID and immediately-preceding position are exact;
2. offset records are canonical and self-contained;
3. expected signer public key(s) are exact;
4. the signed message is valid UTF-8 JSON for the expected closed object;
5. RFC 8785 canonicalization of the parsed object is byte-for-byte identical to
   the signed message;
6. `SHA-256(signed_message)` equals the instruction `voucher_hash` or
   `binding_hash`;
7. every authority-bearing payload field matches authoritative state/current
   program/current instruction values;
8. timestamp/lifecycle/funding/sequence/conservation rules pass.

The program therefore **consumes** FC-PROTO-006 bytes; it does not rebuild a
semantically equivalent JSON object and ask the signer to sign a second
profile.

## Voucher binding rules

The parsed canonical voucher payload must match:

```text
domain                       foundry.channels.voucher
protocol_version             1.0.0
environment                  state.environment runtime mapping
network                      solana:devnet for the beta profile
genesis_hash                 state.genesis_hash encoded as base58
program_id                   current ChannelVault program ID
channel_id                   SHA-256(UTF-8 value) == state.channel_id_hash
channel_account              current ChannelState PDA
epoch                        state.epoch
sequence                     instruction.sequence
previous_activated_hash      state.latest_activated_voucher_hash
sender                       state.sender
recipient_claim_pubkey       state.recipient_claim_pubkey
mint                         state.mint
cumulative amount            instruction.cumulative_authorized
expires_at                   instruction.voucher_expiry
```

`issued_at` remains descriptive as already decided by the protocol. It must be
a valid canonical timestamp, but it is not evidence of signature creation time.

## Recipient-binding rules

The parsed canonical binding payload must match:

```text
domain                  foundry.channels.recipient-binding
protocol_version        1.0.0
environment/network     authoritative runtime profile
genesis_hash            state.genesis_hash
program_id              current program
channel_id              hash matches state.channel_id_hash
channel_account         current ChannelState PDA
epoch                   state.epoch
claim_pubkey             state.recipient_claim_pubkey
voucher_hash             state.latest_activated_voucher_hash
mint                     state.mint
binding_mode             initial
destination_wallet       instruction.destination_wallet
binding_nonce            canonical integer decoded from instruction/state slot
```

`claim_id` is part of the exact signed payload but is not an independent
on-chain authority key in v1; both the fixed claim key and destination wallet
must sign the identical closed payload. Its syntax/canonicality is still
validated.

Binding expiry must be valid at `Clock::unix_timestamp`. Initial binding remains
one-use because a successfully bound channel cannot bind again.

## Canonical binding-nonce encoding

The existing 32-byte account field remains byte-for-byte unchanged. Runtime v1
account semantics define one canonical integer container:

```text
bytes[0..8]   = u64 little-endian
bytes[8..32]  = 0
```

The initial binding nonce is `1`. Any non-zero tail is rejected by the runtime
profile. This mapping exists only to bridge the already-frozen fixed-width
account field to the already-frozen FC-PROTO-006 JSON integer; it does not alter
either representation.

## Evidence required

The functional correction must publish deterministic evidence covering:

- v1 vectors remain byte-identical;
- v2 initialize serialization and round-trip;
- v2 known/unknown version rejection;
- message extraction from canonical one- and two-signature Ed25519 layouts;
- non-canonical JSON rejection;
- canonical payload hash mismatch rejection;
- sequence/cumulative/destination substitution rejection even when the
  Ed25519 signature instruction itself is structurally valid;
- channel/program/network/epoch/mint/sender/claim-key substitution rejection;
- binding nonce integer ↔ fixed-slot round-trip and non-zero-tail rejection.

## Relationship to FC-SOL-006

`FC-SOL-006` is blocked until this correction is integrated. Afterward it may
consume the v2 runtime profile while continuing to preserve and test the v1
historical transport vectors.

This correction does not itself implement a Solana entrypoint, perform CPI,
deploy a program, or authorize devnet deployment.
