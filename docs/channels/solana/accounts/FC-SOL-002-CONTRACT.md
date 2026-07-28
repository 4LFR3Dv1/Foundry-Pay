# FC-SOL-002 — ChannelVault account contract

Status: ready for experimental implementation  
Authority: local validator only  
External Solana account review: not performed

## Objective

FC-SOL-002 freezes and implements only where the v1 channel state lives and how
it is represented:

```text
ChannelState PDA
        │ authority
        ▼
classic SPL Token vault account
```

It does not define who may economically mutate that state. Instruction
authority, signature-precompile mapping, transfers, and lifecycle transitions
belong to FC-SOL-003 and later gates.

## Minimal topology

The v1 one-sender/one-recipient fixture has exactly:

1. one program-owned `ChannelState` PDA; and
2. one canonical classic SPL Token account whose authority is that PDA.

There is no separate `RecipientBinding`, `SettlementState`, or `ClosureState`
account. Decomposition requires a later ADR demonstrating a concrete
concurrency, lifecycle, or storage need.

## Fixed-width `ChannelState`

Variable-width serialization is prohibited. `String`, `Vec<T>`, and
`Option<T>` must not appear in the account layout. Optional conditions use a
closed `u8` flag plus a fixed-width value.

The implementation must preserve this field order and publish the exact
primitive encoding and byte offset of every field:

```text
discriminator: [u8; 8]
account_version: u16
bump: u8
status: u8
environment: u8
network: u8
program_version: u16
policy_flags: u32

genesis_hash: [u8; 32]
channel_nonce: [u8; 32]
channel_id_hash: [u8; 32]

epoch: u64
sender: Pubkey
recipient_claim_pubkey: Pubkey
recipient_wallet: Pubkey
recipient_bound: u8
binding_nonce: [u8; 32]

mint: Pubkey
vault_token_account: Pubkey
decimals: u8

funded_total: u64
activated_authorized_total: u64
settled_total: u64
refunded_total: u64

latest_activated_sequence: u64
latest_activated_voucher_hash: [u8; 32]

channel_expiry_set: u8
channel_expiry: i64
voucher_expiry_set: u8
voucher_expiry: i64
close_requested: u8
close_requested_at: i64
claim_deadline_set: u8
claim_deadline: i64

reserved: [u8; 64]
```

All multi-byte integers use the serialization encoding selected and documented
by the program framework; golden vectors make that choice normative. Status,
environment, network, and flags use closed numeric mappings. Booleans encoded
as `u8` accept only `0` or `1`.

`CHANNEL_STATE_VERSION_V1` is `1`. The 64 reserved bytes provide two
32-byte slots of migration headroom without reallocating the v1 account. They
must be zero in v1 and cannot acquire meaning without a version change and ADR.

The functional PR must derive and publish `CHANNEL_STATE_SPACE` from the exact
layout, including the eight-byte discriminator, and prove that it equals the
real serialized length. This coordination contract deliberately does not guess
the numeric total before the implementation and framework encoding exist.

## PDA derivation

The v1 PDA seeds are raw bytes:

```text
[
  b"channel",
  sender_pubkey_bytes,
  mint_pubkey_bytes,
  channel_nonce_32
]
```

No Base58 or other textual intermediate participates in derivation. The random
nonce reduces pre-disclosure enumeration but provides no confidentiality after
the address is known.

Golden vectors cover exact program ID, sender, mint, nonce, resulting PDA, and
bump, plus one-field mutations and multiple channels for the same sender/mint.

## Token-account boundary

The experimental fixture supports classic SPL Token only:

```text
supported: classic SPL Token
unsupported: Token-2022, transfer fees, transfer hooks, rebasing-like behavior
```

The future account validator must fail closed unless the supplied vault has the
expected canonical address, classic token-program owner, fixed mint, and
`ChannelState` PDA authority. FC-SOL-002 represents and validates this
relationship but performs no token transfer or CPI.

## Space and rent

Account space is normative. The rent-exempt lamport minimum is environmental.
Evidence must record:

```text
CHANNEL_STATE_SPACE
Rent::minimum_balance(CHANNEL_STATE_SPACE)
toolchain and local-validator context
```

No protocol rule may depend on a copied, permanent lamport constant.

## Required vectors and rejection cases

Serialized golden vectors cover:

- zero initialized;
- funded active;
- closing with a bound recipient.

Each records binary bytes, hexadecimal, Base64, byte length, SHA-256, field
offsets, and decoded values.

Malformed cases include wrong discriminator, unknown version, short and
unauthorized long lengths, unknown status, non-zero reserved bytes, substituted
mint or vault, invalid boolean flags, and inconsistent recipient-bound fields.
Full economic transition invariants remain FC-SOL-004 scope.

## Evidence

The functional work item publishes:

```text
evidence/runs/FC-SOL-002/
├── README.md
├── TASK_CONTRACT.yaml
├── account-layout-v1.json
├── account-field-offsets-v1.json
├── pda-vectors-v1.json
├── serialized-golden-vectors-v1.json
├── malformed-account-matrix.json
├── token-account-authority-report.json
├── rent-space-report.json
├── toolchain-report.json
├── cargo-test.xml
├── validation-report.json
└── artifact-manifest.json
```

## Non-goals and stop conditions

Stop if this phase introduces variable-width state, unversioned fields,
text-derived PDA seeds, implicit Token-2022 support, semantic use of reserved
bytes, instructions, CPI, transfers, Ed25519 verification, devnet deployment,
mainnet, or real-value use.

The only allowed public claim after successful completion is:

> The experimental ChannelVault account model has a versioned fixed-width
> layout, deterministic PDA derivation, pinned token-account authority rules,
> and reproducible golden vectors under a local-validator-only authorization.
