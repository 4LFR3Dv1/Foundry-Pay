# FC-SOL-003A — ChannelVault ABI implementability correction

Status: ready  
Baseline: FC-SOL-003 merge `192bd40245244cfd540c67f880104259b5190379`

FC-SOL-003A is a narrow pre-runtime correction. It must:

1. add the exact System, classic Token, and Associated Token programs to
   `initialize_channel`, and make the sender a writable signer/payer;
2. declare `settle` permissionless while fixing its destination to the bound
   recipient's canonical ATA;
3. enforce a 900-second minimum and 2,592,000-second maximum exclusive claim
   window in the pure contract model;
4. regenerate account-meta, positive, negative, validation, and artifact
   evidence.

It must not change instruction bytes, discriminators, canonical preimages,
Ed25519 layouts, PDA seeds, or the 490-byte account layout.

It must not implement entrypoints, handlers, CPI, token transfers, RPC,
deployment, wallet, or consumer behavior.

