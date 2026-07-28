# FC-SOL-003 evidence

This bundle proves the experimental ChannelVault instruction contract under
deterministic local fixtures.

It contains:

- an isolated instruction-contract crate that depends on, but does not mutate,
  the FC-SOL-002 account-model crate;
- eight atomic instruction serializations and account-meta contracts;
- exact Ed25519 precompile layouts for one-signature vouchers and
  two-signature recipient bindings;
- stable lifecycle, event, and error registries;
- positive and adversarial negative fixtures;
- reproducible hashes and test reports.

Boundaries:

- no entrypoint or economic handler;
- no CPI or SPL transfer;
- no RPC, wallet, signer service, or deployment;
- no deployable Anchor IDL;
- external Solana instruction and Ed25519 review not performed;
- devnet, mainnet, and real-value use blocked.

The allowed claim is limited to a frozen and self-validated experimental
instruction contract. It is not an operational ChannelVault.
