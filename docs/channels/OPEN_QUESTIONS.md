# Open questions

These questions do not reopen accepted authority boundaries. Each is a gated
implementation choice.

| ID | Question | Default until resolved | Owner/work item | Stop condition |
|---|---|---|---|---|
| FC-OQ-001 | Exact Rust/Borsh encoding corresponding to canonical voucher payload | no program implementation | FC-PROTO-006 / FC-SOL-003 | Python, TypeScript, and Rust bytes differ |
| FC-OQ-002 | Require sequences to increase by exactly one or allow gaps with hash chaining | exact +1 for MVP | FC-PROTO-002 | gap weakens audit/recovery |
| FC-OQ-003 | Claim-key generation and secure browser storage API | WebCrypto-compatible Ed25519 where supported; otherwise wallet/client flow | FC-SEC-003 | secret reaches server/log |
| FC-OQ-004 | Optional identity verification for “person” semantics | bearer capability only; UI must say so | FC-PROD-004 | product claims verified human identity |
| FC-OQ-005 | Rebinding in MVP | disabled | FC-PROTO-003 | binding loss blocks required pilot |
| FC-OQ-006 | Minimum close grace and maximum voucher lifetime | conservative test constants only | FC-PROTO-005 | sender can strand/revoke live right |
| FC-OQ-007 | Upgrade authority governance | devnet key for iteration; no production claim | FC-SOL-005 | mainnet or production proposal without multisig/timelock/immutability decision |
| FC-OQ-008 | Fresh fixture mint or prior devnet mint | fresh fixture preferred | FC-SOL-001 | mint authority/provenance unavailable |
| FC-OQ-009 | Event design for indexer reconstruction | account state authoritative; events supplemental | FC-SOL-003 | reconstruction requires Cloud-only data |
| FC-OQ-010 | L2 provider and eventual L3 source | two independent devnet providers | FC-SEC-005 / validation | evidence claims independence without diverse source |
| FC-OQ-011 | Sponsored activation fee policy | product convenience only | private product | relay fee logic changes signed amount/right |
| FC-OQ-012 | Formal verification toolchain | property tests first; formal methods required before production claim | FC-SOL-004 | conservation/replay uncertainty remains material |
| FC-OQ-013 | Durable operation ID collision semantics | persist `operation_id → canonical operation commitment hash`; same ID with different bytes is `OPERATION_CONFLICT` | future execution-preparation coordination | handler or SA-CHAN-002/003 proceeds with ID-only deduplication |

## Resolved by foundation

- cumulative funded unidirectional primitive;
- issued versus activated voucher semantics;
- on-chain economic authority;
- Cloud non-authority;
- external Solana-Agent boundary;
- claim-key plus wallet binding;
- old-sequence rejection after activation;
- close grace preserving outstanding rights;
- no automatic rebroadcast from ambiguity;
- public/private repository split.
