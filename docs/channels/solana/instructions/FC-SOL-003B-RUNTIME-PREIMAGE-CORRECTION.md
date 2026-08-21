# FC-SOL-003B — Runtime signed-preimage operability correction

Status: implementation self-validated, integration review pending  
Scope: transport/runtime authority only  
Entry point: not implemented here  
CPI / token transfer: not implemented here  
Deployment: not authorized here

## Problem

The historical v1 instruction transport is reproducible and remains valid as
historical protocol evidence, but it is insufficient for a safe ChannelVault
runtime.

For example, v1 `activate_voucher` independently carries `sequence`,
`cumulative_authorized`, `voucher_hash`, and `voucher_expiry`, while the exact
FC-PROTO-006 sender-signed payload binds a larger authority domain including:

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
sequence
previous_activated_voucher_hash
sender
recipient_claim_pubkey
mint
cumulative_authorized_base_units
issued_at
expires_at
```

A runtime must not verify one signed message and then accept a separate
instruction field as economic authority unless that field is proven to be the
same value inside the signed message.

Recipient binding has the same class of problem. In addition, historical v1
initialization does not carry all immutable identity fields later required to
bind those signed objects to ChannelState.

## Non-negotiable compatibility boundary

FC-SOL-003B does not rewrite the existing protocol. It preserves:

```text
ChannelState size                 490 bytes
ChannelState v1 field offsets     unchanged
ChannelState discriminator        unchanged
PDA seeds                         unchanged
FC-PROTO-006 voucher bytes        unchanged
FC-PROTO-006 binding bytes        unchanged
operation names                   8, unchanged
operation discriminators          unchanged
Ed25519 layout                    unchanged
instruction v1 codec              unchanged
```

The existing `instruction.rs` remains the v1 codec. Runtime v2 is a separate
module and version.

## Runtime instruction contract v2

Every v2 instruction uses the same operation discriminator as v1 followed by:

```text
instruction_contract_version = u16 little-endian = 2
```

The operation registry remains closed to the same eight names.

### initialize_channel v2

Payload, after discriminator/version:

```text
channel_nonce             [u8; 32]
recipient_claim_pubkey    Pubkey / 32 bytes
decimals                  u8
channel_expiry            i64 little-endian
genesis_hash              [u8; 32]
channel_id_hash           [u8; 32]
environment               u8
policy_flags              u32 little-endian
binding_nonce             u64 little-endian
```

Exact payload length: `150` bytes. Exact full instruction length: `160` bytes.

This fills immutable ChannelState identity without changing ChannelState itself.

`channel_id_hash` is normative:

```text
SHA-256(UTF-8(channel_id))
```

The channel identifier must satisfy the existing closed identifier shape before
hashing.

The initial binding nonce is `1` and maps into the existing fixed
`binding_nonce: [u8; 32]` account field as:

```text
bytes[0..8]  = u64 little-endian
bytes[8..32] = all zero
```

A non-zero tail is invalid. The initial latest activated voucher hash remains
the 32-byte protocol zero hash.

### fund_channel v2

Payload remains one checked `u64` amount.

### activate_voucher v2

The instruction carries only:

```text
voucher_hash [u8; 32]
```

`sequence`, `cumulative_authorized_base_units`, and `expires_at` are derived
from the exact sender-signed message after verification. They are not accepted
as a second independently supplied authority source.

### bind_recipient v2

The instruction carries only:

```text
binding_hash [u8; 32]
```

The destination wallet and binding nonce are derived from the exact
recipient-binding payload. The destination must also equal the public key in
the second Ed25519 signature record.

### settle / close / refund / finalize

Their transport fields remain fixed-width operational inputs because they are
not the FC-PROTO-006 signer-preimage mismatch addressed by this work item.
Their economic/lifecycle validation remains the responsibility of FC-SOL-006.

## Exact Ed25519 message extraction

The existing native Ed25519 layout is preserved.

Voucher extraction requires:

- native Ed25519 program ID;
- the Ed25519 instruction immediately precedes ChannelVault;
- one signature;
- self-contained `u16::MAX` instruction references;
- exact frozen offsets;
- exact sender public key.

It returns the bytes beginning at the frozen voucher message offset `112`.

Binding extraction requires:

- the same position/program conditions;
- two signatures;
- exact frozen two-signature offsets;
- exact claim public key;
- both message copies have identical bytes.

It returns both the exact signed message and the destination wallet public key
from the second Ed25519 record.

No compact replacement signer profile is introduced.

## Signed voucher authority validation

The exact extracted message is accepted only when all of these hold before any
future mutation:

1. SHA-256 of the exact message equals the v2 `voucher_hash` commitment;
2. the object has the exact frozen voucher field set;
3. the message has the canonical byte representation required by the frozen
   FC-PROTO-006 voucher profile;
4. domain and protocol version are exact;
5. environment and network match the supported devnet profile;
6. genesis hash matches ChannelState;
7. program ID is the actual program ID supplied by runtime context;
8. channel account is the actual ChannelState account;
9. `SHA-256(UTF-8(channel_id))` equals stored `channel_id_hash`;
10. epoch, sender, recipient claim key, and mint equal ChannelState;
11. previous activated voucher hash equals ChannelState;
12. sequence is a positive JSON-safe integer;
13. cumulative authorization is a canonical unsigned decimal u64 string;
14. timestamps are real UTC-second timestamps and expiry is after issue time.

Only after those checks does the pure verifier return the sequence, cumulative
authorization, voucher hash, and expiry for FC-SOL-006 to apply through its
lifecycle/conservation rules.

## Signed recipient-binding authority validation

The binding verifier applies the equivalent domain/state checks and additionally
requires:

- `binding_mode == "initial"`;
- claim key equals ChannelState claim key;
- voucher hash equals the latest activated voucher hash;
- destination in the payload equals the second Ed25519 public key;
- binding nonce is positive, JSON-safe, and maps exactly to the stored fixed
  32-byte nonce;
- both Ed25519 signatures cover byte-identical payloads.

Only then does it return destination, nonce, hash, and expiry.

## Canonical-byte implementation scope

FC-PROTO-006 defines RFC 8785 JCS off-chain. FC-SOL-003B does **not** introduce
or claim a general-purpose on-chain RFC 8785 implementation.

The Rust verifier handles only the two frozen runtime signer profiles:
`ChannelVoucher` and initial `RecipientBinding`. Their schemas are closed and
the authority-bearing field representations are constrained to ASCII literals,
Base58 public keys/hashes, canonical unsigned decimal amount strings,
JSON-safe unsigned integers, and strict UTC-second timestamps.

For these frozen profiles, parsing and deterministic sorted-key serialization
must reproduce the original bytes exactly. Any whitespace, different key order,
unknown/missing field, wrong type, or other byte representation that does not
reproduce is rejected. The frozen FC-PROTO-006 canonical positive vectors are
used directly in the Rust tests.

A future wider JSON/domain profile must not silently inherit this validator. It
requires its own explicit contract/version and conformance evidence.

## Evidence observed for the functional head

Functional head:

```text
3876f26f155bfeecf322390c31543104aecc1ebe
```

GitHub Actions run:

```text
32494273091
```

Observed results:

- static checks passed;
- secret guard passed over 645 files;
- full Python protocol suite: 576 passed;
- External Execution Protocol TypeScript: 8 passed;
- Channel Protocol TypeScript: 20 passed;
- Python conformance: passed;
- TypeScript conformance: passed;
- Rust conformance: passed;
- cross-language exact-byte/hash comparison: passed;
- expected-output poisoning/independence lane: passed.

The full Python suite includes the foundation checker contract test and the
instruction-contract test that executes the Rust crate with `cargo test
--locked --lib`.

## Byte-stability observations

The v1 instruction source blob is identical in `main` and the functional branch:

```text
programs/foundry-channel-vault/instruction-contract/src/instruction.rs
Git blob: a2f71cf5cd5923260a34fc8f797688aa4bf658df
```

The ChannelState source blob is also identical:

```text
programs/foundry-channel-vault/src/state.rs
Git blob: d6e2f07e607051db4855a99b27adc2e4fda1c7d2
CHANNEL_STATE_SPACE = 490
```

This is source/blob identity evidence, not an external security audit.

## Maturity boundary

After successful integration, the allowed claim is:

> The runtime transport has an explicit v2 profile that binds voucher and
> initial recipient-binding authority to the exact existing FC-PROTO-006 signed
> bytes while preserving the v1 ChannelState and historical instruction codec.

It does **not** prove or authorize:

- an operational ChannelVault entrypoint;
- a token CPI or economic effect;
- local-validator execution of handlers;
- a devnet Program ID or deployment;
- mainnet;
- custody;
- external security review;
- production-value use.
