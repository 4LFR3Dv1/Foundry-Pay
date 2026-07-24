# Glossary

| Term | Meaning |
|---|---|
| Activated voucher | Sender voucher accepted as the latest monotonic state by ChannelVault |
| Activated authorized total | Maximum cumulative amount currently settleable before subtracting prior settlements |
| Binding nonce | Monotonic one-use counter preventing recipient-binding replay |
| Channel | Funded one-way relationship between one sender and one recipient claim key for one mint |
| ChannelVault | Future Solana program and PDA/vault accounts enforcing channel rights |
| Claim key | Ed25519 bearer capability used to authorize initial destination binding |
| Claim link | Protected locator plus client-side claim material |
| Cloud | Private hosted convenience layer; not the economic rights authority |
| Cumulative voucher | Signed total-to-date authorization, not an additive payment |
| Epoch | Formal voucher sequence namespace; reset only after prior rights are finalized |
| Execution authorization | Short-lived single-use approval bound to exact prepared Solana bytes |
| Foundry-Pay public | Apache-2.0 protocols, reference implementations, tests, and evidence |
| Funded total | All fixed-mint units transferred into the channel across open and top-ups |
| Issued voucher | Correctly signed sender voucher not yet activated on-chain |
| Persistent channel link | Relationship/status link containing no claim private material |
| Receive link | Public human address used for discovery; grants no value |
| Recipient binding | Dual-signed operation connecting claim capability to an exact wallet |
| Reconciliation | Independent comparison of observed chain effect with authoritative obligation |
| Remaining right | Activated authorized total minus settled total |
| Settled total | Cumulative units transferred from vault to bound recipient |
| Solana-Agent | Independent external executor responsible for Solana preparation, submission, recovery, and technical evidence |
| Technical receipt | Executor observation used as evidence input, not final business success |
| Unallocated capacity | Funded total minus refunds minus activated authorized total |
| Vault balance | Current fixed-mint token balance held by the Channel PDA's token account |
