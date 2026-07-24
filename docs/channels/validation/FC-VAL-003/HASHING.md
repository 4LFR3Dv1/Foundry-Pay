# Normative research hashes

Protocol version: `fc-val-003-v1`.

All hashes in this protocol use SHA-256 over a domain-separation prefix followed
by RFC 8785 JSON Canonicalization Scheme bytes. Strings are preserved exactly;
implementations must not apply Unicode normalization. The canonical JSON bytes
are UTF-8 and the prefix terminator is one zero byte (`0x00`).

## Run manifest

Domain:

```text
foundry.channels.research.run-manifest.v1
```

Preimage procedure:

1. Parse the approved manifest as JSON.
2. Reject unknown or missing fields with `run-manifest.schema.json`.
3. Remove only the top-level `manifest_sha256` member.
4. Canonicalize the remaining object with RFC 8785.
5. Compute:

```text
SHA256(
  UTF8("foundry.channels.research.run-manifest.v1") ||
  0x00 ||
  RFC8785(manifest_without_manifest_sha256)
)
```

Store the lowercase result as `sha256:<64 hex>`. Recompute it before the first
recruitment contact and reject the run on mismatch. File hashes inside
`protocol_file_hashes` are ordinary SHA-256 over the exact repository bytes,
also rendered as `sha256:<64 hex>`.

## Stage A lock

Domain:

```text
foundry.channels.research.stage-a-lock.v1
```

The private lock object has exactly this shape:

```json
{
  "protocol_version": "fc-val-003-v1",
  "run_id": "FCVAL003-7KQ9M2WX",
  "record_id": "7KQ9M2WX4RTY",
  "responses": {
    "Q1": "exact private response",
    "Q2": "exact private response",
    "Q3": "exact private response",
    "Q4": "exact private response",
    "Q5": "exact private response",
    "Q6": "exact private response"
  },
  "primary_scores": {
    "A1": 2,
    "A2": 2,
    "A3": 2,
    "A4": 2,
    "A5": 2,
    "A6": 2
  }
}
```

No timestamps, Stage B answers, secondary scores, adjudicated scores, identity,
contact data, or consent artifacts enter this preimage. Compute:

```text
SHA256(
  UTF8("foundry.channels.research.stage-a-lock.v1") ||
  0x00 ||
  RFC8785(stage_a_lock_object)
)
```

Store only the resulting `sha256:<64 hex>` in
`stage_a.locked_record_sha256`. The preimage remains pseudonymous private
research data. Before Stage B, a separate process or reviewer must parse the
stored private lock object, recompute the hash, compare it byte-for-byte, and
record success in the private audit trail. A mismatch blocks the session.

## Failure behavior

Unknown fields, missing fields, invalid UTF-8, non-I-JSON values, canonicalizer
failure, file-hash mismatch, or digest mismatch fail closed. Do not repair,
normalize, or silently reserialize a locked record after Stage B is visible.
