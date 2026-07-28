# FC-CTRL-023 evidence

This coordination freezes the FC-SOL-003 contract before any ChannelVault
instruction implementation.

It records:

- eight atomic v1 instruction names;
- account-meta requirements;
- exact, immediately preceding, self-contained Ed25519 layouts;
- lifecycle phases derived without changing the 490-byte ChannelState;
- stable event/error and adversarial-vector requirements;
- self-validation with external review not performed;
- local fixtures/local validator allowed, with devnet, mainnet, real value,
  transfers, and deployment blocked.

No runtime, entrypoint, CPI, transfer, canonical preimage, account layout, PDA
derivation, or deployment authorization changed.
