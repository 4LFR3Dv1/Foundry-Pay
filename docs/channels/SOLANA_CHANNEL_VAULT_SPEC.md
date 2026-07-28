# ChannelVault program specification

- Status: design only
- Implementation authorized by: future `FC-SOL-*` work items
- MVP cluster: devnet

No Solana program is implemented by `FOUNDATIONS-001`.

## Accounts

### Channel account

Proposed fields:

```text
discriminator
account_version
bump
status
environment/network discriminator
genesis_hash
program_version
channel_nonce
channel_id_hash
epoch
sender
recipient_claim_pubkey
recipient_wallet + bound flag
binding_nonce
mint
vault_token_account
decimals
funded_total
activated_authorized_total
settled_total
refunded_total
latest_activated_sequence
latest_activated_voucher_hash
channel_expiry
voucher_expiry
close_requested_at + flag
claim_deadline + flag
policy flags and numeric limits
```

Use checked `u64` amounts only if the supported mint and totals fit; otherwise
the program design must explicitly adopt wider checked arithmetic before
implementation. No saturating arithmetic.

### Vault token account

Associated token account for the channel PDA and fixed mint. The program checks:

- Token Program ownership;
- exact mint;
- authority equals Channel PDA;
- no substituted source/destination accounts.

## PDA derivation

```text
["channel", sender, mint, channel_nonce_32]
```

`channel_nonce_32` is random and public after creation. Its purpose is
anti-enumeration before disclosure, not confidentiality.

## Instructions

### `initialize_channel`

Inputs: nonce, claim public key, mint, expiry, policy, channel ID hash.

Signers: sender, which is also the writable rent payer.

Accounts also include the exact System Program, classic SPL Token Program, and
Associated Token Program. Effects: create the 490-byte Channel PDA with
`invoke_signed`, create its canonical vault ATA idempotently, initialize
genesis/latest voucher hash and zero totals, and enter `funding`.

### `fund_channel`

Inputs: amount.

Signers: sender/funding authority.

Effects: transfer checked fixed mint to vault, increase funded total, verify
conservation, activate channel after minimum funding.

### `activate_voucher`

Inputs: canonical voucher payload bytes/hash and sender signature evidence.

Signers: fee payer/relay; sender transaction signature is optional if the
Ed25519 precompile verifies the voucher signature.

Effects: verify Ed25519 instruction from the instructions sysvar, exact sender
key/message/hash, monotonic sequence/total, previous hash, funding, policy, and
expiry; update activated state.

The Ed25519 precompile is a top-level instruction, not a CPI target. The program
must inspect the transaction instruction data and reject ambiguous offset or
instruction-index layouts.

### `bind_recipient`

Inputs: binding payload and claim/destination signature evidence.

Effects: verify both Ed25519 signatures, claim public key, binding nonce,
unbound state, exact destination, epoch, network/program/channel, and expiry;
persist recipient wallet.

### `settle`

Inputs: requested amount, voucher sequence/hash.

Signers: none required by the ChannelVault instruction. Settlement is
permissionless after binding.

Effects: check activated state, lifecycle, expiry, totals, destination ATA, and
conservation; require the destination to equal the canonical ATA of the bound
recipient and fixed mint; transfer checked via PDA-signed CPI; increment
settled total. A caller cannot redirect value or create a right.

### `request_close`

Signers: sender.

Effects: stop top-up, store claim deadline and the activated snapshot at
request time, and enter `closing`. Voucher activation and settlement remain
allowed until the on-chain claim deadline. It cannot reduce a right.

The deadline is exclusive and must satisfy checked fixed experimental bounds:

```text
900 <= claim_deadline - Clock::unix_timestamp <= 2_592_000
```

### `activate_voucher` while closing

Signers/evidence: the same sender-signed voucher proof as normal activation.

Effects: before `claim_deadline`, apply the normal signature, domain, program,
channel, epoch, sequence, previous-hash, amount, funding, policy, and expiry
checks. The program does not trust `issued_at` as proof of signature creation
time. A valid voucher presented before the deadline may advance the activated
total.

### `refund_excess`

Signers: sender.

Effects: reject before `claim_deadline`. After the deadline, activation is
closed and only capacity not reserved by the final activated right may be
refunded.

### `finalize_close`

Signers: sender.

Effects: after claim deadline and relevant expiry, refund remaining eligible
balance, close vault and channel according to explicit rent destination rules.

### `rebind_recipient`

Not in initial MVP unless `current_and_new_wallet` policy is implemented.
Requires current and new wallet signatures, exact payload, and monotonic nonce.

## On-chain errors

At minimum:

```text
InvalidDomain
UnsupportedVersion
WrongNetworkOrProgram
WrongChannelOrEpoch
WrongSenderOrRecipient
WrongMintOrTokenAccount
InvalidVoucherSignature
InvalidBindingSignature
StaleVoucherSequence
PreviousVoucherHashMismatch
CumulativeAmountDecreased
AuthorizationExceedsFunding
SettlementExceedsAuthorization
SettlementExceedsVault
ClaimAlreadyBound
BindingNonceReplay
VoucherExpired
ChannelExpired
ChannelClosing
OutstandingRightReserved
ArithmeticOverflow
InvalidLifecycleTransition
```

Every error occurs before economic effect.

## Concurrency

Solana account write locks serialize transactions mutating the same Channel
account. The program must still re-check all totals inside the instruction.
Two competing settlements cannot both use the same pre-state because the later
transaction observes updated `settled_total` or fails.

## Upgrade and governance

Devnet begins upgradeable for iteration. Before any production consideration:

- publish program ID, source commit, IDL hash, binary verification method, and
  program data/authority;
- move upgrade authority to an independently controlled multisig with timelock
  and documented emergency process, or make the program immutable after audit;
- define account migration and version compatibility;
- reject unknown account and instruction versions;
- test malicious and incompatible upgrades.

No production, audit, or mainnet claim follows from this specification.

## Official references

- [Solana programs and mutable state accounts](https://solana.com/docs/core/programs)
- [Ed25519 precompiled program](https://solana.com/docs/core/programs/precompiles)
- [Calling the Token Program via CPI](https://solana.com/docs/tokens/advanced/cpi)
- [Deploying and managing upgrade authority](https://solana.com/docs/programs/deploying)
