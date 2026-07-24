# Normative state machines

## Channel

```text
draft → funding → active
active → settling → active
active → closing → closed
funding → expired
active → expired
```

Exceptional states reachable from nonterminal states:

```text
blocked
disputed
needs_recovery
needs_review
```

| From | Event | Guard | To |
|---|---|---|---|
| draft | open accepted | identities, mint, claim key, policy, expiry valid | funding |
| funding | minimum funding observed | conservation holds and vault owns correct mint | active |
| funding | expiry | no outstanding right | expired |
| active | top up | same sender/mint/channel | active |
| active | voucher activated | signature, monotonicity, funding, policy, expiry | active |
| active | settlement starts | bound wallet and positive remaining right | settling |
| settling | reconciled effect | observed totals equal expected | active |
| settling | unknown result | persisted signature or broadcast ambiguity | needs_recovery |
| settling | source divergence | material observations disagree | disputed |
| needs_recovery | signature confirmed and reconciled | no rebroadcast | active |
| needs_recovery | proven rejection before acceptance | policy review | needs_review |
| active | close requested | freeze latest activated state | closing |
| closing | partial/final settlement | before claim deadline, outstanding right | closing |
| closing | excess refund | refund <= unallocated capacity | closing |
| closing | final refund and finalize | deadline+expiry passed, no reserved right | closed |

`closed` is terminal. No transition from exceptional states may happen without
an explicit observation, review decision, or recovery result.

## Claim

```text
created
→ delivered
→ opened
→ identity_verified
→ destination_bound
→ settlement_ready
→ settled
```

Exceptional:

```text
expired
revoked
blocked
already_claimed
```

`identity_verified` means product-level verification, if configured. It does
not replace the cryptographic claim-key and destination-wallet binding.

| From | Event | Guard | To |
|---|---|---|---|
| created | locator delivered | no secret logged | delivered |
| delivered | client opens | valid opaque locator | opened |
| opened | optional identity check | policy-specific evidence | identity_verified |
| opened/identity_verified | bind | claim-key + wallet signatures, nonce unused | destination_bound |
| destination_bound | activated right available | on-chain voucher state matches | settlement_ready |
| settlement_ready | full right reconciled | settled total reaches authorized total | settled |
| any pre-settled | time expiry | authoritative clock | expired |
| created/delivered | revoke unactivated delivery | no activated right is removed | revoked |
| opened+ | reused binding | nonce or wallet already bound | already_claimed |

A sender cannot revoke an activated economic right by changing Cloud claim
state.

## Settlement

```text
requested
→ preparing
→ simulated
→ authorized
→ signing
→ submitted
→ confirming
→ reconciling
→ completed
```

Lateral states:

```text
failed
needs_recovery
needs_review
rejected
```

| From | Event | Guard | To |
|---|---|---|---|
| requested | prepare | obligation and channel snapshot current | preparing |
| preparing | simulation succeeds | exact instruction and policy valid | simulated |
| simulated | Foundry authorizes | hashes, constraints, expiry match | authorized |
| authorized | signer claims grant | single-use and exact-byte binding | signing |
| signing | signature persisted | exact signed transaction durable | submitted |
| submitted | RPC observation pending | no second broadcast | confirming |
| submitted/confirming | response unknown | persisted signature | needs_recovery |
| confirming | confirmed/finalized | signature observed | reconciling |
| needs_recovery | status finds signature | no retransmission | reconciling |
| needs_recovery | not found after expiry | independent reconciliation required | needs_review |
| reconciling | totals match | source policy satisfied | completed |
| reconciling | sources disagree | preserve evidence | needs_review |
| pre-signing | definitive validation failure | no network effect possible | rejected |
| preparing/simulated | transient local failure | new attempt requires policy | failed |

`failed` never implies that an ambiguous broadcast is safe to retry.

## Voucher activation

```text
issued → activation_requested → validating → activated
                                   ├→ rejected
                                   └→ needs_review
```

There is no transition from `activated` back to `issued`, revoked, or a lower
sequence. Closing freezes the latest activated state.

## Restart rules

- Every off-chain state change is journaled before its external effect.
- `signing`, `submitted`, `confirming`, and `needs_recovery` survive restart.
- Orphaned in-progress operations become interrupted/recovery states, never
  fresh automatic attempts.
- On-chain state remains the source of truth for channel accounting.
