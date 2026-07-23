# Foundry Pay Program

## Product wedge

Reconciliation and controlled remediation for stablecoin operations.

## Proof milestone

One synthetic divergence is corrected on Solana devnet through the external
Solana-Agent without duplicated economic effect, with authorization bound to
the exact message bytes, L2 reconciliation, and a verifiable evidence bundle.

## Critical path

1. Operational control and ADR.
2. Protocol schemas, normalization, hashing, and conformance.
3. Fake executor and failure recovery.
4. Solana-Agent JSONL gateway.
5. Exact authorization and signer boundary.
6. Devnet execution, reconciliation, and evidence.

Circle, Arc, Stellar, KeeperHub, and Tether remain outside the critical path
until the proof milestone exists.
