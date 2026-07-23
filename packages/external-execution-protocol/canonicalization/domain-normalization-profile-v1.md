# Domain Normalization Profile v1

Profile identifier: `foundry-pay-domain-v1`.

## General rules

- Signed objects are closed: unknown properties are rejected.
- Optional properties are absent, never `null`.
- Amounts are unsigned base-unit integers encoded as decimal strings.
- Numeric strings have no leading zero except the value `0`.
- Floating-point values are forbidden in signed objects.
- Network identifiers come from the protocol schema.
- Solana addresses are canonical base58 encodings of exactly 32 bytes.
- Timestamps use UTC RFC 3339 with second precision:
  `YYYY-MM-DDTHH:MM:SSZ`.
- Material arrays retain their declared order.
- The profile identifier participates in every economic plan hash.
- After domain validation, JSON is canonicalized with RFC 8785.

## EconomicPlan v1

Required key set:

```text
protocol_version
normalization_profile
obligation_id
network
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
