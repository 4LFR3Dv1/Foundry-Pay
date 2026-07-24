# Reuse and gap matrix

| Required component | Origin | Current state | Reuse decision | Required change | Risk | Evidence |
|---|---|---|---|---|---|---|
| External execution envelope | Solana-Agent | implemented | reuse without modification | advertise channel capabilities through versioned extension | Low | `gateway/protocol.py`, gateway tests |
| Gateway idempotency journal | Solana-Agent | implemented | reuse without modification | channel correlation fields remain inside payload | Low | `gateway/journal.py`, chaos tests |
| Local policy engine | Solana-Agent | implemented | extend | add ChannelVault program/account/operation constraints | Medium | `authority/policy.py`, policy tests |
| Exact-message preparation | Solana-Agent | SPL transfer implemented | generalize adapter | construct ChannelVault instructions and decode accounts | High | `gateway/solana_prepare.py`, live evidence |
| Signature-first execution | Solana-Agent | implemented | reuse without modification | accept channel-prepared messages through existing commitment | Medium | `gateway/solana_execute.py`, execution tests |
| Status and recovery | Solana-Agent | implemented | reuse without modification | add channel account observations to evidence, not retry logic | Medium | gateway recovery and chaos evidence |
| Technical evidence | Solana-Agent | implemented for transfer/counter | extend | extract Channel, vault, recipient, sequence, and totals | Medium | `adapters/evidence.py`, `docs/evidence/` |
| Domain canonicalization | Foundry-Pay | implemented for economic plan | generalize with new profile | channel/voucher/binding closed types and byte vectors | High | Python/TS canonicalization tests |
| External execution protocol | Foundry-Pay | implemented | reuse without modification initially | channel settlement becomes a new economic capability | Medium | protocol schemas/vectors |
| Execution authorization | Foundry-Pay | implemented | extend constraints only | understand allowed ChannelVault program and exact expected accounts/totals | High | authorization tests/live proof |
| Exact-message signer | Foundry-Pay | implemented | reuse without modification | no channel business logic in signer | Low | signer boundary/tests |
| Reference reconciliation | Foundry-Pay | transfer implemented | extend | compare Channel fields plus vault/recipient deltas | High | reconciliation tests/L1-L2 evidence |
| Fake executor | Foundry-Pay | durable effect model | reuse patterns; extend fixtures | add reference channel ledger and cumulative operations | Medium | fake executor tests |
| Failure lab | Foundry-Pay | implemented | extend scenarios | activation, binding, concurrent settlement, close/refund | Medium | failure and chaos matrices |
| Evidence manifest | Foundry-Pay | run manifests exist | generalize | normative `ChannelEvidence` and claim-level evidence | Medium | `docs/EVIDENCE.md`, evidence runs |
| Channel object schemas | none | missing | create | frozen public contracts | High | `contracts/channel/channel.schema.json` |
| Cumulative voucher verifier | none | missing | create | Python/TS/Rust canonical bytes and signature verification | Critical | voucher schema and planned vectors |
| Recipient claim/binding verifier | none | missing | create | dual signature, nonce, expiry, rebind policy | Critical | binding/claim schemas |
| Reference channel ledger | none | missing | create | deterministic conservation and lifecycle state machine | High | future FC-PROTO work |
| ChannelVault program | none | specified only | create later | accounts, instructions, CPI, arithmetic, signatures | Critical | `SOLANA_CHANNEL_VAULT_SPEC.md` |
| Channel SDKs | none | missing | create after protocol | Cloud-free inspect/bind/settle/recover | High | repository topology decision |
| Receive-link resolver | private Cloud | missing | create privately | signed versioned profile resolution | High | product experience/threat model |
| Claim relay | private Cloud | missing | create privately | opaque locator, encrypted payload, no secret logs | Critical | link ADR/threat model |
| Settlement orchestrator | private Cloud | missing | create privately | durable correlation with public protocol | High | authority/failure model |
| Consumer UX | private Cloud | missing | create privately | hide protocol complexity and expose recovery truthfully | High | product experience |

## Summary

Reuse is strongest below the channel business layer:

```text
exact authorization + signer + submission + recovery + reconciliation
```

New work is concentrated in:

```text
channel rights + voucher activation + recipient binding + on-chain conservation
```

No evidence supports rewriting the existing execution, signer, recovery, or
reconciliation kernels.
