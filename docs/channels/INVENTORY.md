# Technical inventory

## Baselines

The inventory was produced from clean immutable public revisions:

| Repository | Commit | Merge |
|---|---|---|
| Solana-Agent | `914eaf3c9b407f787c6f51d9886c6e86ae542335` | PR #12 |
| Foundry-Pay | `a8631b081f40029c18b16098508c44540efbf77f` | PR #13 |

## Solana-Agent

| Surface | Existing implementation | Evidence |
|---|---|---|
| Closed gateway | five-command JSONL envelope, strict fields/version | `gateway/protocol.py`, `tests/test_external_gateway.py` |
| Durable transport journal | reserve-before-dispatch, replay/conflict/recovery | `gateway/journal.py`, `gateway/service.py` |
| Backend boundary | `prepare`, execute, status, recover, evidence protocol | `gateway/backend.py` |
| SPL preparation | devnet TransferChecked message, simulation, commitment | `gateway/solana_prepare.py`, `tests/test_solana_prepare_backend.py` |
| Signature-first execution | exact authorization/message validation, persisted signature, one send | `gateway/solana_execute.py`, `tests/test_solana_execute_backend.py` |
| Chaos recovery | process kill, lost response, no redispatch | `gateway/chaos.py`, `gateway/chaos_scenario.py`, `docs/chaos-testing.md` |
| Command journal | planned→validated→running→terminal with artifacts | `solana_agent/execution/journal.py`, `tests/test_command_journal.py` |
| Local policy | default deny, cluster/path/wallet/spend/secret guards | `solana_agent/authority/policy.py`, `tests/test_policy_engine.py` |
| Bound approvals | exact command/policy hash, expiry, single-use | `solana_agent/authority/approvals.py`, `tests/test_policy_engine.py` |
| Redaction | key/value and text secret filtering | `solana_agent/authority/redaction.py` |
| Solana/RPC adapters | allowlisted clusters and structured operations | `solana_agent/adapters/solana_cli.py`, `solana_agent/adapters/solana_rpc.py` |
| Evidence | deploy/invoke/RPC evidence adapters and public proof | `solana_agent/adapters/evidence.py`, `docs/evidence/` |
| Reproducible environment | pinned toolchain and validator integration | `toolchain.lock.json`, `environment/`, integration tests |

Current gateway scope is `solana.spl_transfer.v1` on devnet. Channel capabilities
do not exist.

## Foundry-Pay public

| Surface | Existing implementation | Evidence |
|---|---|---|
| External Execution Protocol | closed schemas for plan, preparation, authorization, receipt/status/recovery | `packages/external-execution-protocol/schemas/` |
| Canonicalization | RFC 8785, closed objects, address/time/amount validation, SHA-256 domains | `canonicalization.py`, `canonicalization.ts`, conformance tests |
| Cross-language vectors | Python and TypeScript positive/negative agreement | `conformance/vectors/`, `tests/protocol/` |
| Fake executor | SQLite durability, idempotent obligation, exact binding, replay rejection | `fake_executor.py`, `test_fake_executor.py` |
| Authorization authority | rebuild commitment, enforce constraints/TTL, durable single-use grant | `services/authorization/authority.py`, authorization tests |
| Signer boundary | authorization verification, exact bytes, durable claim, restart/recovery | `services/signer/boundary.py`, signer tests |
| Reconciliation | source registry, normalized L1/L2/L3 observations, disagreement preservation | `services/reconciliation/`, reconciliation tests |
| Failure lab | durable state, signature-first order, unknown outcome, event hash chain | `services/failure_lab/`, failure tests |
| Real-process chaos | RPC proxy and independent journal root | `services/chaos_proxy/`, `services/process_chaos/`, chaos tests |
| Public evidence | live devnet transfer, L1/L2, failure matrices | `evidence/runs/`, `docs/EVIDENCE.md` |
| Licensing boundary | Apache-2.0 public work and explicit private operated layer | `LICENSE`, `NOTICE`, `docs/PUBLIC_COMMERCIAL_BOUNDARY.md` |

Current economic normalization is specialized to
`solana.spl_transfer.v1`. Channel objects, verifier, ledger, program, and SDKs
do not exist.

## Attack surface at foundation time

There is no Foundry Channels listener, frontend, Cloud service, or program yet.
Current executable entry points relevant to reuse are:

| Entry point | Type | Authentication/authority | Validation |
|---|---|---|---|
| `solana-agent-gateway` stdin/stdout | local JSONL process | Foundry authorization public key + external signer boundary | strict envelope and closed domain objects |
| Solana RPC outbound calls | external JSON-RPC | no RPC trust authority | allowlisted devnet, normalized observations |
| Foundry authorization API as Python service boundary | in-process reference | injected signature provider | closed prepared execution and constraints |
| Exact-message signer API as Python service boundary | in-process reference | authorization verifier + configured signer | exact hashes/bytes, time, single-use |
| chaos proxy | localhost test listener | test-only | disabled by default and fixture controlled |

The future claim link, consumer frontend, Cloud APIs, and ChannelVault program
are threat-model targets, not current deployed attack surfaces.

## Existing claims and limits

Demonstrated:

- devnet exact-message SPL transfer;
- durable authorization/signing/submission/recovery behavior;
- two-source reconciliation;
- deterministic and process-level failure matrices.

Not demonstrated:

- any channel object or ChannelVault instruction;
- cumulative activation;
- claim key or wallet binding;
- channel conservation/refund;
- Cloud outage recovery for a channel;
- mainnet, production, custody, audit, or scale.
