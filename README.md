# Foundry Pay

Governed stablecoin reconciliation and controlled remediation.

[![CI](https://github.com/4LFR3Dv1/Foundry-Pay/actions/workflows/ci.yml/badge.svg)](https://github.com/4LFR3Dv1/Foundry-Pay/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](pyproject.toml)
[![Status: pre-alpha](https://img.shields.io/badge/Status-pre--alpha-orange.svg)](ROADMAP.md)

Foundry Pay coordinates economic approval, exact-message authorization,
external execution, independent reconciliation, recovery, and verifiable
evidence. It lets an application remediate a known stablecoin obligation
without giving a network executor authority to invent or broaden the economic
intent.

The public repository is an Apache-2.0 reference implementation and
proof-of-work. It is not a production custody system or a managed payment
service.

## Why Foundry Pay

Stablecoin operations can diverge across internal ledgers, processors, and
blockchains. Correcting that divergence safely requires more than sending a
transaction:

- the business obligation must be approved independently;
- authorization must bind the exact message that will be signed;
- an ambiguous broadcast must be recovered before any new attempt;
- a network receipt must be reconciled against the original obligation;
- the completed result must be supported by reproducible evidence.

Foundry Pay separates those responsibilities so that a specialized executor can
operate on Solana without becoming the economic authority.

## Who it is for

- payment and stablecoin teams designing controlled remediation;
- wallet, custody, or treasury engineers evaluating exact-message boundaries;
- Solana executor developers implementing the External Execution Protocol;
- security and reliability engineers testing ambiguous transaction outcomes;
- contributors building protocol schemas, conformance tooling, and sanitized
  evidence.

## Five-minute local proof

Requirements: Git, Python 3.11 or newer, and an internet connection for the
initial package install. No wallet, Solana CLI, RPC endpoint, token, or funds are
required.

```text
git clone https://github.com/4LFR3Dv1/Foundry-Pay.git
cd Foundry-Pay
python -m venv .venv
```

Activate the environment:

```text
# PowerShell
.venv\Scripts\Activate.ps1

# bash/zsh
source .venv/bin/activate
```

Install and run the deterministic proof:

```text
python -m pip install -e .
python examples/local_proof.py
```

The example prepares an exact message, issues a short-lived single-use
authorization, simulates a lost response after a durable effect, recovers the
receipt, and rejects replay. Successful output includes:

```json
{
  "economic_effect_count": 1,
  "may_rematerialize": false,
  "recovery_outcome": "confirmed",
  "replay_blocked": true,
  "response_lost_after_commit": true
}
```

The hashes in the full output bind the economic plan, prepared message,
execution commitment, and receipt.

## Architecture

```text
Foundry Pay                   External executor             Signer
economic authority           network specialist            exact-byte boundary
global policy                local safety policy            no business authority
approval + authorization  →  prepare/simulate/execute  →   sign commitment only
reconciliation               status/recover/evidence
```

Foundry Pay owns:

- economic intent and global policy;
- economic approval and execution authorization;
- independent reconciliation and the final business result.

An external executor owns:

- network-specific preparation and simulation;
- locally governed transmission and technical confirmation;
- signature-first recovery and technical evidence.

Executor receipts are evidence inputs, not declarations of business success.
Free-form prompts never cross the execution boundary.

Read the [architecture](docs/ARCHITECTURE.md) and the
[external-first decision](docs/ADR/FP-ADR-001-external-first.md) for the
normative authority split.

## Canonical reconciliation flow

```text
observe divergence
→ create economic plan
→ approve plan
→ external executor prepares and simulates exact message
→ authorize exact execution commitment
→ signer validates and signs exact bytes
→ executor broadcasts once
→ recover if outcome is unknown
→ reconcile network observations against the obligation
→ publish hash-bound evidence
```

Objects are versioned and correlated by `execution_request_id`,
`obligation_id`, `economic_plan_hash`, `prepared_message_hash`, and
`execution_commitment_hash`.

## Supported public components

| Component | Current capability |
|---|---|
| External Execution Protocol | JSON schemas, deterministic canonicalization, and conformance vectors |
| Python reference package | Hashing, fake authority, and durable fake executor |
| TypeScript reference package | Cross-language canonicalization verification |
| Authorization service | Short-lived, single-use exact-message grants |
| Signer boundary | Rejects changed, expired, or mismatched material |
| Reconciliation service | Source-diverse L1/L2 observations and deterministic outcomes |
| Failure labs | Response loss, restart, RPC failure, concurrency, and recovery matrices |
| Evidence index | Sanitized claims, artifacts, limitations, and residual gates |

The JSONL transport is an initial adapter, not part of the domain authority
model.

## Executors

The deterministic fake executor is included for local development and
conformance testing.

[Solana-Agent](https://github.com/4LFR3Dv1/Solana-Agent) is the first independent
reference consumer of the External Execution Protocol. It remains a separate
Apache-2.0 public good and is not imported into Foundry Pay.

## Failure and recovery model

Foundry Pay treats an unknown broadcast result as `needs_recovery`. It never
assumes failure and never automatically materializes or broadcasts a
replacement message while the earlier obligation may have executed.

The public failure suites cover:

- failure before signature persistence;
- restart after signature persistence;
- response loss after broadcast acceptance;
- blockhash expiry and definitive RPC rejection;
- concurrent recovery attempts;
- source unavailability and later reconciliation convergence.

See [failure recovery](docs/FAILURE_RECOVERY.md) and
[process chaos](docs/PROCESS_CHAOS.md).

## Public evidence

The first governed Solana proof completed one approved SPL transfer of
`1,000,000` base units on devnet. Exact-message authorization, one broadcast,
L1/L2 reconciliation, and a nine-scenario failure matrix are published as
sanitized evidence.

This proves the current protocol path; it does not establish mainnet or
production readiness.

The [evidence index](docs/EVIDENCE.md) separates demonstrated claims from open
gates. A correlated public snapshot is also available in the
[Solana-Agent evidence directory](https://github.com/4LFR3Dv1/Solana-Agent/tree/main/docs/evidence).

## Development

Install all development dependencies:

```text
python -m pip install -e ".[dev]"
npm ci --prefix packages/external-execution-protocol/typescript
```

Run the same core checks as CI:

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
npm test --prefix packages/external-execution-protocol/typescript
```

Repository governance, work-item contracts, path reservations, and evidence
requirements are documented in [AGENTS.md](AGENTS.md) and the
[work graph](docs/WORK_GRAPH.md). These are maintainer controls, not
prerequisites for evaluating the five-minute local proof.

## Current status

Foundry Pay is pre-alpha proof-of-work:

- deterministic protocol and recovery tests are available;
- a governed Solana devnet remediation has been demonstrated;
- production custody, L3 observation, sustained operation, mainnet use, and
  external security review remain open.

See the public [roadmap](ROADMAP.md) and [changelog](CHANGELOG.md).

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. By
participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

Do not report vulnerabilities through a public issue. Follow
[SECURITY.md](SECURITY.md) and use GitHub's private vulnerability reporting
channel.

## Public and commercial boundary

The public protocol, reference implementations, deterministic services, tests,
documentation, sanitized fixtures, and evidence are Apache-2.0 open source.

Production credentials, customer data, custody and key infrastructure, private
risk rules, proprietary connectors, deployment configuration, and managed
operations are not included in this repository. This architectural boundary
does not restrict the Apache-2.0 rights granted for public code.

Read the complete
[public/commercial boundary](docs/PUBLIC_COMMERCIAL_BOUNDARY.md) and its
[licensing ADR](docs/ADR/FP-ADR-002-open-source-boundary.md).

## License

Foundry Pay content for which the licensor holds the necessary rights is
licensed under the [Apache License 2.0](LICENSE). Copyright attribution is in
[NOTICE](NOTICE). Third-party materials retain their respective licenses and
attribution requirements; see
[third-party notices](provenance/THIRD_PARTY_NOTICES.md).
