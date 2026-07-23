# FP-FAIL-002: real-process chaos verification

FP-FAIL-002 moves failure testing across real operating-system process and HTTP
boundaries:

```text
Foundry process harness
  → Solana-Agent JSONL gateway subprocess
  → persistent localhost fault proxy subprocess
  → persistent Solana JSON-RPC upstream subprocess
```

The Solana-Agent checkout is pinned to
`5707240af22bc288149b68456b2a9fe810928efb`. It remains an external repository;
no executor kernel code is copied into Foundry Pay.

## Safety claim

The verified property is:

> At-most-one `sendTransaction` request by the controlled runtime, with
> signature-first recovery and no automatic rematerialization under
> uncertainty.

The matrix does not claim exactly-once execution or atomicity between SQLite,
HTTP, an RPC provider, and Solana.

## Persistent RPC proxy

`services.chaos_proxy` binds only to localhost. It stores each JSON-RPC request
and hash-chained proxy event in an independent SQLite database before applying a
fault. It records:

- request receipt and request hash;
- upstream forwarding;
- upstream response hash and persistence;
- whether a response reached the client;
- whether a response was deliberately dropped;
- definitive rejection before forwarding;
- per-method counters.

Supported fault rules are:

- `pass`;
- `reject_before_forward`;
- `drop_before_forward`;
- `drop_after_upstream`;
- `delay_after_upstream`;
- `return_null_status`.

The proxy journal is independent from the Solana-Agent gateway journal. The
cross-check between its `sendTransaction` counter and the gateway's durable
state is the core evidence.

## Nine scenarios

1. **Kill before durable claim:** the gateway exits after full validation but
   before signature/broadcast-intent persistence. Proxy send count is zero and
   preparation remains queryable.
2. **Kill after durable broadcast intent:** signature, signed transaction, and
   intent are persisted; process exits before RPC. Recovery is
   `needs_recovery`, automatic send is forbidden, proxy send count is zero.
3. **Kill during `sendTransaction`:** upstream accepts, proxy delays the
   response, and the gateway process is killed. Restart recovers the persisted
   signature as confirmed; proxy send count is one.
4. **Response lost after acceptance:** proxy persists the upstream response and
   closes the client connection. Restart returns `recovered_confirmed` without
   another send.
5. **Definitive rejection:** proxy returns a JSON-RPC error before forwarding.
   Gateway records `failed/definitive_rejection`, distinct from uncertainty.
6. **Not found after expiry:** the client connection drops before forwarding,
   both the status observation and expiry policy remain explicit, and recovery
   reports `not_found_after_expiry_needs_reconciliation`. Rematerialization
   remains a Foundry decision.
7. **Replay after restart:** the same JSONL request returns the durable error
   response with `replayed=true`; proxy send count remains one.
8. **Two gateway processes:** two real JSONL processes share one SQLite journal.
   `BEGIN IMMEDIATE` yields one winning execution claim, one conflict/recovery
   response, and one proxy send.
9. **Independent source convergence:** L2 unavailability first produces
   `l1_verified + pending`; the later matching L2 produces `l2_verified`.
   Both results and their hashes remain in history. Unavailability is never
   mislabeled as disagreement.

## Test keys and upstream

The process matrix uses ephemeral Solana and Foundry test keypairs created
inside the scenario driver. Private bytes never cross JSONL, never reach the
proxy, and never enter reports. Only public keys and signatures are emitted.

The deterministic matrix terminates at a persistent emulated Solana JSON-RPC
upstream. It tests real subprocess, pipe, socket, SQLite, timeout, restart, and
concurrency behavior without spending funds or depending on devnet stability.
FP-E2E-001 remains the live devnet execution proof; FP-REC-001 remains the live
two-provider observation proof.

## External checkpoint

Every scenario report is SHA-256 hashed. `journal-root.json` binds the ordered
artifact list, Foundry implementation commit, and pinned Solana-Agent commit.
GitHub Actions publishes this file as an artifact named with the workflow commit
SHA. This places the checkpoint outside the local journal domain.

The next strengthening step is a signed Sigstore attestation or an on-chain
checkpoint. Neither is claimed by FP-FAIL-002.

## Canonical demo

`master-demo.json` contains only the most legible scenario:

```text
upstream accepts sendTransaction
→ proxy persists response and delivers nothing
→ gateway returns needs_recovery
→ gateway restarts
→ recover(signature) returns recovered_confirmed
→ proxy sendTransaction count remains 1
→ rebroadcasts = 0
```
