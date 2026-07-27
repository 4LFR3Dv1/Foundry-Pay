# Foundry Channels canonicalization v1

## Normative pipeline

For a validated normative projection `P`:

```text
canonical_bytes_v1(P) = RFC8785_JCS(P)
canonical_hash_v1(P) =
  "sha256:" + lowerhex(SHA256(canonical_bytes_v1(P)))
```

Validation precedes canonicalization. Producers and verifiers MUST NOT remove
unknown fields, insert defaults, infer domains, coerce types, normalize
Unicode, reorder arrays, or translate `null` into absence.

## Wire parsing

Wire JSON MUST be UTF-8 and MUST reject duplicate property names, `NaN`,
`Infinity`, `-Infinity`, invalid UTF-8, and malformed JSON. Parsing is distinct
from schema validation. A parsed in-memory mapping does not prove that its wire
representation lacked duplicate keys.

## JSON domain

- Objects are closed. Missing required fields and unknown fields are rejected.
- Optional fields are omitted. `null` is rejected unless a schema explicitly
  permits it.
- Strings are encoded as UTF-8. Lone UTF-16 surrogates are rejected.
- Unicode is not normalized. NFC and NFD strings remain different byte
  sequences and hashes.
- Floats, negative zero, and non-finite numbers are rejected.
- JSON integer fields are limited to `0..9007199254740991` unless their schema
  explicitly permits signed values.
- Boolean values never satisfy integer fields.
- Economic values are decimal strings matching `^(0|[1-9][0-9]*)$`; u64
  economic fields additionally require
  `0..18446744073709551615`.
- Timestamps use exactly `YYYY-MM-DDTHH:MM:SSZ` and must describe a real UTC
  calendar instant.

Escapes with the same parsed JSON string produce the same JCS bytes. Unicode
normalization-equivalent but byte-distinct strings do not.

## Arrays

Every array is classified by its object profile:

- `ordered_sequence`: received order is preserved and material.
- `canonical_set`: elements must be unique and already sorted by the declared
  key. Non-canonical order is rejected; it is never repaired silently.

`observation_hashes`, `provider_ids`, `artifact_hashes`, and authority lists
are canonical sets when registered as such. Journal events and ordered
execution steps are ordered sequences.

## Hash text and verification

Hash text MUST match `^sha256:[0-9a-f]{64}$`. Uppercase hexadecimal, missing
prefixes, extra whitespace, and wrong lengths are rejected before comparison.
Verification uses exact textual equality after both values independently pass
the canonical format check.

## Self-hash exclusion

For a self-hashed record `R` with registered field `h`:

```text
preimage = R excluding exactly h
R[h] = canonical_hash_v1(preimage)
```

The field must exist in the supplied record. No recursive or heuristic removal
occurs. Any additional field remains in the preimage.

## Raw bytes

Binary material uses:

```text
raw_bytes_hash_v1(B) =
  "sha256:" + lowerhex(SHA256(B))
```

`B` must be a non-empty byte string when required by the object contract. Its
domain separation lives in the validated commitment object that references the
raw digest, never in an ad-hoc byte prefix added by this primitive.
