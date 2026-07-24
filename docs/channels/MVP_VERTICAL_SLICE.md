# MVP vertical slice

## Purpose

Demonstrate one complete channel without adding production or mainnet scope.

## Fixture

- cluster: Solana devnet;
- genesis hash: devnet value verified at execution time;
- asset: six-decimal synthetic SPL fixture;
- baseline example mint:
  `2tUzxADKHWxwTpihHuuzwfoGhYBY7735s2QXEuUcNX3k`;
- funded amount: `100000000` base units;
- cumulative updates: `10000000`, `25000000`, `40000000`;
- one existing sender wallet and one existing recipient wallet;
- protected claim capability generated client-side.

The existing mint is a prior devnet fixture, not a mainnet USDC claim.
Implementation may mint a fresh deterministic test fixture and must record its
authority and provenance.

## End-to-end flow

### 1. Open and fund

- sender creates claim key and random channel nonce;
- ChannelVault PDA and vault ATA are derived;
- sender approves exact open/fund economic plan;
- Solana-Agent prepares and simulates;
- exact message is authorized and signed;
- one transaction opens and funds 100 fixture units;
- Foundry reconciles Channel and vault totals.

Expected:

```text
F=100, A=0, S=0, R=0, V=100
status=active
```

### 2. Activate cumulative updates

Sender signs and activates:

```text
seq=1, A=10
seq=2, A=25
seq=3, A=40
```

Each activation references the latest activated voucher hash. Negative attempts
with sequence 1/2, amount 39, wrong mint, wrong channel, or stale previous hash
are rejected without effect.

Expected:

```text
F=100, A=40, S=0, R=0, V=100
latest_sequence=3
```

### 3. Deliver and bind

- recipient opens claim link;
- locator resolves public metadata;
- client reads private claim key from fragment;
- recipient connects existing wallet;
- claim key and wallet sign identical binding payload;
- ChannelVault stores destination wallet and consumes binding nonce.

Substitution and repeated binding fail.

### 4. Settle 40 with response loss

- recipient requests 40;
- Foundry creates exact settlement obligation;
- Solana-Agent prepares and simulates ChannelVault settle;
- Foundry verifies and authorizes exact message;
- signer signs exact bytes;
- Solana-Agent persists signature and submits once;
- injected RPC proxy loses the successful response;
- executor transitions to `needs_recovery`;
- recovery finds signature and account state without retransmitting;
- L1/L2 reconciliation verifies Channel and token deltas.

Expected:

```text
F=100, A=40, S=40, R=0, V=60
outstanding=0
unallocated=60
status=active
provider broadcast calls=1
```

### 5. Continue channel

Channel remains open. Sender may activate a higher cumulative total up to 100
or top up before a larger authorization.

## Evidence bundle

Must include:

- program ID, account addresses, mint, participants, and cluster genesis;
- signed voucher payloads/hashes/signatures with private material removed;
- binding payload/hash/signatures with claim private material removed;
- exact execution plans, prepared message hashes, simulations, commitments,
  authorizations, and signer receipts;
- transaction signatures and account snapshots before/after;
- gateway/executor journal and fault injection counters;
- L1/L2 observations and reconciliation result;
- manifest with SHA-256 for every artifact;
- video showing product language and recovery behavior.

## Acceptance

- all positive transitions occur;
- all defined negative vectors reject without effect;
- old voucher sequences add no value after sequence 3 activation;
- settlement total never exceeds 40;
- controlled broadcast call count is one under response loss;
- final accounting is 100 = 60 + 40 + 0;
- Cloud can be stopped before recovery and public tools still verify the right
  and result.

## Explicit non-claims

The slice does not prove mainnet, production, custody, audit, scale, real USDC,
mobile readiness, or exactly-once distributed execution.
