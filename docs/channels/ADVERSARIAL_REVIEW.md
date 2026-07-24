# Adversarial foundation review

Date: 2026-07-24  
Scope: `FOUNDATIONS-001` design, contracts, boundaries, and execution plan  
Disposition: acceptable for narrow offline protocol implementation; not
approved for a Solana program, hosted service, mainnet, or custody.

## Review questions and findings

### Can Cloud fabricate a recipient right?

No under the accepted design. A right requires a sender-signed, domain-separated
voucher and program activation. Cloud can withhold, delay, or censor delivery,
which is an availability risk, but cannot increase the signed amount or activate
an altered payload.

### Can an old signed voucher be globally invalidated off-chain?

No. Treating the newest object seen by one server as globally authoritative
would reintroduce server trust. The design therefore distinguishes issued from
activated vouchers; ChannelVault's monotonic sequence is the invalidation
authority. This adds an activation transaction but removes a central ambiguity.

### Does a stolen claim link transfer value by itself?

The fragment contains a bearer claim secret, so theft remains serious. Initial
binding additionally requires a signature from the destination wallet, but an
attacker with both link access and their own wallet could bind first. Controls
must include high-entropy locators, fragment-only secret handling, short
unbound expiry, one-time binding nonce, user-visible destination confirmation,
revocation before binding, CSP/dependency hardening, and incident recovery.
This remains a critical residual risk until `FC-SEC-003` is independently
reviewed.

### Can sender closure erase an already activated right?

No. Closing freezes the activated total, preserves the outstanding right during
the explicit claim window, and refunds only unallocated capacity immediately.
Final refund of expired outstanding value depends on an explicit expiry rule.

### Can two settlement requests race?

ChannelVault must serialize account writes and compare both activated and
settled totals. Clients must regard account lock/contention as a retryable
pre-submission condition only. After any possible submission, persisted
signature recovery is mandatory before another attempt.

### Can Solana-Agent become the business authority?

No. It receives a closed execution request and exact authorization, applies
local fail-closed safety, and returns technical evidence. Foundry Pay performs
economic approval and independent reconciliation. A technical receipt is not a
business success declaration.

### Does the topology force an early monorepo rewrite?

No. The accepted topology is incremental: channel contracts and documentation
are namespaced in the current public repository; packages and the program are
created only by approved work items. Solana-Agent remains external. Cloud code
is never placed here.

## Blocking findings for later phases

1. Do not implement ChannelVault until Rust/Borsh bytes match Python and
   TypeScript canonical test vectors.
2. Do not implement a browser claim flow until fragment leakage, analytics,
   third-party scripts, referrers, logs, backups, and recovery have an
   independently reviewed control plan.
3. Do not claim safe closure until property tests cover outstanding rights,
   expiry, top-up, settlement races, and refund conservation.
4. Do not propose mainnet while upgrade authority, custody, signer compromise,
   RPC diversity, incident response, and external audit remain unresolved.
5. Do not call the flow exactly-once; use persisted-signature recovery and
   reconciliation language.

## Scope-pressure attacks rejected

- embedding business policies in Solana-Agent;
- making Cloud's database the rights ledger;
- putting secrets or voucher payloads directly in URL query parameters;
- adding custody, swaps, cross-chain, native mobile, fiat, or multi-tenant
  billing to the MVP;
- copying execution or reconciliation kernels into a channel package;
- implementing the Solana program before canonical bytes and invariants freeze.

## Result

The foundation is coherent enough for `FC-PROTO-001` through
`FC-PROTO-003` to begin as offline reference implementations. The five ready
items preserve independent review surfaces and do not require reopening the
channel primitive, authority split, or public/private boundary.
