# FP-FAIL-001 evidence

Implementation commit: `cd7e733583216c1900305b50393f100892b3e667`

This directory contains nine deterministic failure reports generated from
isolated SQLite journals:

1. lost response after accepted broadcast;
2. restart before signature persistence;
3. restart after signature persistence;
4. recovery RPC unavailable;
5. broadcast outcome unknown;
6. blockhash expired before broadcast;
7. known RPC rejection before acceptance;
8. repeated recovery without a second broadcast;
9. L1/L2 reconciliation divergence.

Every execution report contains its final durable state, signature-persistence
flag, broadcast count, economic-effect count, rematerialization decision, and
hash-chained journal events. The divergence report preserves the complete
reconciliation aggregate.

`manifest.json` binds each report by SHA-256 and proves:

- all broadcast counts are at most one;
- all unresolved outcomes forbid rematerialization;
- all nine scenarios were generated.

Reproduce from the repository root:

```text
python -c "from pathlib import Path; from services.failure_lab import write_failure_evidence; root=Path.cwd(); write_failure_evidence(root, root/'evidence/runs/FP-FAIL-001', implementation_commit='cd7e733583216c1900305b50393f100892b3e667')"
python -m pytest tests/failures -q
```
