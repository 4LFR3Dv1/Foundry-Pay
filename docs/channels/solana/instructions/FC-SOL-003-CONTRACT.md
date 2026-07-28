# FC-SOL-003 — ChannelVault instruction contract

Status: ready for experimental contract implementation  
Authority: deterministic local fixtures and local validator only  
External Solana instruction/Ed25519 review: not performed

## Objective

FC-SOL-003 freezes the v1 instruction surface, account metas, authority mapping,
Ed25519-precompile parsing, derived lifecycle phases, events, errors, and
deterministic vectors. It answers who may request each mutation and which exact
accounts and signed bytes must be validated.

It does **not** implement an entrypoint, economic handler, CPI, SPL transfer,
deployment, RPC integration, wallet, consumer flow, or production signer.
FC-SOL-004 remains responsible for proving arbitrary transition sequences.

The fixed 490-byte `ChannelState` from FC-SOL-002 and all FC-PROTO-006
canonical preimages are immutable inputs to this work item.

## Atomic v1 instruction registry

The registry has exactly these operations:

1. `initialize_channel`
2. `fund_channel`
3. `activate_voucher`
4. `bind_recipient`
5. `settle`
6. `request_close`
7. `refund_unallocated`
8. `finalize_close`

Combined operations such as `bind_and_settle` are not part of v1.

Each executable fixture must publish instruction bytes, account metas, expected
pre-state, projected post-state, event, and stable rejection code. Projected
post-state is a contract fixture, not an executed on-chain transition.

## Lifecycle without a layout change

No new byte is added to `ChannelState`. The externally meaningful phases are
derived from the existing closed `StatusCode` and Solana clock:

```text
account absent                         → uninitialized
status = Active                        → active
status = Closing and now < deadline    → closing_open
status = Closing and now >= deadline   → closing_frozen
status = Closed                        → finalized
```

The claim deadline is exclusive: activation is allowed only while
`now < claim_deadline`; freeze/refund eligibility starts at
`now >= claim_deadline`. `finalized` is terminal.

The existing `Funding`, `Settling`, and exceptional status codes remain valid
account encodings, but FC-SOL-003 cannot invent persistent intermediate
transitions for atomic handlers. Any later use requires its own transition
contract and FC-SOL-004 coverage.

During `closing_open`, a valid pre-deadline voucher may still be activated and
activated rights may be settled. During `closing_frozen`, no new activation is
allowed; activated rights remain reserved until settlement. Voucher expiry can
prevent future activation but never extinguishes an activated v1 right.

## Account-meta contract

Every instruction entry freezes, for every account:

- signer or non-signer;
- writable or read-only;
- expected owner or executable program ID;
- PDA derivation and expected address;
- channel/mint/vault relationship;
- lifecycle precondition.

Client-supplied account names and ordering never substitute for validation.
The only token program is classic SPL Token. Token-2022, transfer fees, hooks,
and substituted token programs are rejected.

The v1 topology remains one program-owned `ChannelState` PDA and its canonical
classic SPL Token vault. No recipient, settlement, or closure PDA is added.

## Authority map

| Operation | Authority |
|---|---|
| initialize | sender transaction signer |
| fund | sender transaction signer and exact classic-token accounts |
| activate voucher | sender Ed25519 signature over the exact registered voucher preimage |
| bind recipient | claim key and destination wallet Ed25519 signatures over the same exact binding preimage |
| settle | bound destination account plus validated channel state; no voucher reinterpretation |
| request close | sender transaction signer |
| refund unallocated | sender transaction signer after the exclusive deadline |
| finalize close | sender transaction signer after all terminal guards |

A voucher signature authorizes only cumulative activation. A binding signature
authorizes only recipient binding. No signed object may be interpreted under a
different domain, profile, type, version, or instruction.

## Canonical Ed25519 instruction mapping

Ed25519 verification is a top-level native precompile instruction, not a CPI.
For `activate_voucher` and `bind_recipient`, the precompile must be the
instruction immediately preceding the ChannelVault instruction. The
instructions sysvar is read-only and must have its exact well-known address.

All data references are self-contained: every instruction-index field is
`u16::MAX`. Cross-instruction data references are rejected even though the
native format can express them.

### One-signature voucher layout

```text
byte 0: signature_count = 1
byte 1: padding = 0
bytes 2..16: one 14-byte little-endian offsets record
public key:  offset 16, length 32
signature:   offset 48, length 64
message:     offset 112, exact normative preimage length
total:       112 + message length
```

The public key must equal the channel sender. The message must equal the exact
FC-PROTO-006 voucher preimage. Prefixes, suffixes, trailing bytes, changed
lengths, overlap, out-of-bounds reads, and external instruction references are
rejected.

### Two-signature binding layout

The order is claim key first, destination wallet second. Both independently
sign identical copies of the exact RecipientBinding preimage:

```text
header length H = 2 + (14 * 2) = 30

record 1:
  public key offset = H
  signature offset  = H + 32
  message offset    = H + 96
  message length    = M

record 2:
  public key offset = H + 96 + M
  signature offset  = H + 128 + M
  message offset    = H + 192 + M
  message length    = M

total length = H + 192 + (2 * M)
```

The two message byte ranges do not overlap and must be byte-identical.
All offsets and `M` must fit the native `u16` fields. No trailing data is
accepted.

## Economic guards frozen for later handlers

The instruction contracts must make these guards explicit:

```text
settled_total <= activated_authorized_total
activated_authorized_total <= funded_total - refunded_total
refund <= funded_total - refunded_total - activated_authorized_total
latest sequence advances strictly
binding nonce is consumed at most once
recipient wallet cannot change after binding
mint, vault, classic token program, and PDA authority remain immutable
finalized cannot mutate
```

All future arithmetic is checked. A failed guard emits no success event and
produces no projected state transition.

## Events

The closed v1 event registry is:

```text
ChannelInitialized
ChannelFunded
VoucherActivated
RecipientBound
SettlementExecuted
CloseRequested
RefundExecuted
ChannelFinalized
```

Events describe on-chain facts only. `PaymentCompleted`,
`BusinessObligationSatisfied`, and equivalent business outcomes are forbidden.
No claim secret, full signed payload, credential, or private material enters an
event.

## Error taxonomy

Stable numeric codes are grouped by:

- instruction decoding and unsupported version/profile;
- account, PDA, owner, signer, and executable-program validation;
- mint, vault, classic-token-program, and authority validation;
- lifecycle and expiry;
- Ed25519 program, position, header, offsets, pubkey, and message;
- sequence, replay, binding, and recipient;
- funding, conservation, refund, and checked arithmetic.

Numeric codes are normative. Human-readable strings are not.

## Required negative coverage

Fixtures must reject substituted accounts, missing signers, wrong PDA/owner,
wrong mint, Token-2022, wrong vault authority, incompatible lifecycle, repeated
or regressive sequence, cumulative value above funding, reused binding nonce,
different recipient, expired voucher, unknown version/profile, missing or
non-preceding Ed25519 instruction, changed offset/pubkey/message length, and a
one-byte preimage mutation.

Validation completes before a success event can be projected.

## Evidence

The functional work item publishes:

```text
instruction-registry-v1.json
account-meta-contracts-v1.json
signed-message-mapping-v1.json
ed25519-offset-vectors-v1.json
instruction-serialization-v1.json
event-registry-v1.json
error-registry-v1.json
lifecycle-transition-matrix-v1.json
positive-vectors-v1.json
negative-vectors-v1.json
idl-hash-report.json
validation-report.json
artifact-manifest.json
```

An IDL hash report may hash the frozen transport-neutral registry; it must state
that no deployable Anchor IDL exists if no entrypoint has been implemented.

## Stop conditions

Stop if an offset, index, message boundary, signer, account relationship, or
lifecycle guard remains ambiguous; if handlers, CPI, transfers, deployment,
RPC, wallet, consumer logic, Token-2022, or variable-width state enter scope;
or if the implementation is represented as operational, deployed, audited, or
safe for value.
