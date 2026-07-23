# Domain Normalization Profile v1

Profile identifier: `foundry-pay-domain-v1`.

## General rules

- Signed objects are closed: unknown properties are rejected.
- Optional properties are absent, never `null`; all signed objects reject
  `null`.
- Amounts are unsigned base-unit integers encoded as decimal strings.
- Numeric strings have no leading zero except the value `0`.
- Floating-point values, NaN, Infinity, negative zero, and integers outside
  JavaScript's safe range are forbidden in signed objects.
- Financial values are never represented by JSON numbers.
- The canonical network identifier for the MVP is `solana:devnet`.
- The canonical capability identifier is `solana.spl_transfer.v1`.
- Solana addresses are canonical base58 encodings of exactly 32 bytes.
- Timestamps use UTC RFC 3339 with second precision:
  `YYYY-MM-DDTHH:MM:SSZ`.
- Material arrays retain their declared order.
- Object property order is not material.
- Unicode strings are hashed exactly as supplied. The protocol does not apply
  NFC, NFD, or any other Unicode normalization silently. Canonically equivalent
  Unicode sequences therefore produce different hashes.
- Lone UTF-16 surrogates are rejected.
- The profile identifier participates in every economic plan hash.
- After domain validation, JSON is canonicalized with RFC 8785.

## EconomicPlan v1

Required key set:

```text
protocol_version
normalization_profile
obligation_id
network
capability
asset
amount_base_units
source
destination
expires_at
```

Optional key set:

```text
reason
```

`asset` is a closed object containing `kind = "spl-token"`, canonical `mint`,
and integer `decimals`.

Validation rejects non-canonical input instead of silently rewriting financial
meaning.
