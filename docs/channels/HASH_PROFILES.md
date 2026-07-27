# Foundry Channels hash profiles v1

| Profile | Input | Projection | Exclusion | Authority |
| --- | --- | --- | --- | --- |
| `signed-payload-v1` | closed authority envelope | registered payload object | envelope hash and signatures | signature verifier |
| `canonical-record-v1` | validated operational object | complete registered object | none | object-specific validator |
| `self-hashed-record-v1` | validated record with own hash | complete record without registered own-hash field | exactly one field | reconciler or record producer |
| `journal-chain-v1` | validated journal event | registered event body | `event_hash` only | durable journal |
| `raw-bytes-commitment-v1` | exact bytes | bytes unchanged | none | commitment validator |
| `evidence-artifact-v1` | file bytes | bytes unchanged | none | evidence manifest; non-economic |

## Signed payload

The payload contains an exact registered domain and every economically material
authority field. Envelope signatures and the declared payload hash do not enter
the payload preimage. Mutating any payload field changes the bytes and digest.

## Canonical record

The whole validated object is the projection. Existing v1 operational objects
bind an exact registered `type` plus `protocol_version`; the domain registry
rejects unknown pairs. No field is removed.

## Self-hashed record

Only the registered own-hash field is removed. A receipt signature or
observation signature remains in the preimage unless its object contract
defines a separate signed payload.

## Journal chain

The event preimage is the closed object:

```text
type
protocol_version
settlement_id or refund_id
sequence
state
event_type
payload
previous_event_hash
recorded_at
```

The precise identity field is registered per journal. `event_hash` is excluded.
`payload_hash` is derived independently from the complete payload and is an
output view, not an alternative event-chain preimage.

## Raw bytes and evidence

Raw protocol bytes and evidence files both use SHA-256 over exact bytes, but
their namespaces and authority are different. An evidence manifest digest
never proves an economic right or an execution commitment.
