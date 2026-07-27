# FC-SEC-002 signed authority inventory

This inventory prevents hashes, receipts, and Cloud records from being
misrepresented as direct cryptographic authority.

| Object | Binding in the current model | Authority |
| --- | --- | --- |
| Channel voucher | Direct signature over exact canonical payload | Sender |
| Recipient binding | Two direct signatures over the same exact payload | Claim key and destination wallet |
| Settlement request | Transitive through execution commitment and authorization | Execution authority |
| Settlement execution commitment | Exact hash link consumed by signed authorization | External execution authority |
| Execution authorization | Direct signature over the exact authorized commitment | External execution authority |
| Closure request | Self-hash only in the offline model | Future ChannelVault must require sender transaction authority |
| Refund request | Self-hash plus future execution authorization | Future sender transaction and execution authority |
| Reconciled receipt | Non-authoritative evidence | None |

## What the cross-language harness proves

For the two frozen signed-payload profiles, each implementation independently:

1. loads the frozen source object;
2. changes one structurally valid material field;
3. chooses the exact verifier type, profile, version, and domain;
4. canonicalizes the mutated payload;
5. computes the mutated SHA-256;
6. rejects reuse of the original declared signed-preimage hash;
7. reports zero economic, authority, and lifecycle effects.

It compares real canonical bytes and hashes for preimage mutations. Profile,
version, domain, and type failures reject before canonicalization.

## Explicit limitation

The frozen public fixtures contain signature-shaped strings, not public/private
key test material that permits independent Ed25519 verification. Therefore this
gate does not claim that three Ed25519 implementations verified real
signatures. It proves exact signed-preimage separation and runtime authority
effects. Real transaction and program signature behavior remains a later
Solana-program gate.
