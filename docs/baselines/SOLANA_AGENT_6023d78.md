# Solana-Agent observable baseline

- Work item: `SA-BASE-001`
- Repository: `4LFR3Dv1/Solana-Agent`
- Immutable commit: `6023d78b10b31b47a1beeecd438d67afbc722bd4`
- License: Apache-2.0
- Baseline date: 2026-07-23
- Local state: detached HEAD, clean worktree

## Verified surface

Current CLI commands:

```text
inspect-env
doctor
missions
approvals
commands
run
```

The runtime already exposes observable primitives relevant to the external
protocol:

- command contracts and structured outputs;
- policy evaluation with default deny;
- approvals bound to command and policy inputs;
- idempotency keys;
- persisted command journal;
- SQLite-backed repositories;
- Solana RPC adapter;
- evidence assembly;
- redaction;
- fake executor;
- explicit devnet and signing approval rules.

## Verification result

```text
python -m pytest -q
115 passed, 2 skipped
```

The skipped tests require the pinned Solana/Anchor integration toolchain:

- counter toolchain integration;
- local validator integration.

## Protocol gaps

The baseline does not yet expose the external protocol commands:

```text
prepare
authorize-and-execute
status
recover
evidence
```

It also does not yet prove:

- Domain Normalization Profile v1;
- RFC 8785 equality with Foundry Pay;
- `economic_plan_hash`;
- SHA-256 over exact serialized Solana message bytes;
- `execution_commitment_hash`;
- external `ExecutionAuthorization`;
- recovery keyed by `execution_request_id`;
- prohibition on rematerialization while broadcast outcome is unknown.

## Integration decision

Do not modify or extract the existing kernel during protocol design.

Implement a thin gateway only after the fake executor passes the independent
conformance kit. Existing local policy, approvals, journal, and adapters remain
Solana-Agent internals unless an explicit later ADR approves a shared library.
