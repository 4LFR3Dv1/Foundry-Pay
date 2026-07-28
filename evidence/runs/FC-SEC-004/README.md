# FC-SEC-004 evidence

Reproduce:

```text
python evidence/runs/FC-SEC-004/generate_evidence.py \
  --baseline 39e067965955f5389153eb05d4fe436cf5d13444 \
  --implementation-commit f87e6d466722ca6a67b09f84ab1817154340bf85
```

The evidence covers versioned snapshot preparation, conditional commit,
duplicate operation IDs, stale rejection, commit-time temporal revalidation,
serial replay witnesses, and derived vault conservation.

It is an offline model only. It does not prove Solana account locking,
transaction scheduling, CPI rollback, a real SPL balance, local-validator
behavior, deployment, formal verification, or external review.
