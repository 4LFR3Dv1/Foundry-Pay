# FC-SOL-003A evidence

This run republishes the ChannelVault v1 account-meta registry after the narrow
operability correction in FC-ADR-010.

It proves:

- `initialize_channel` has sufficient metas for future atomic ChannelState PDA
  and canonical classic-token ATA creation;
- settlement is permissionless while its destination remains the bound
  recipient canonical ATA;
- the exclusive claim window accepts exactly 900 through 2,592,000 seconds
  using checked arithmetic;
- instruction serialization, signed preimages, Ed25519 layouts, PDA seeds, and
  the 490-byte account layout are unchanged.

No entrypoint, handler, CPI, transfer, deployment, or external review is
included.

