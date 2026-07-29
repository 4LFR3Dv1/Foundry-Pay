# FC-CTRL-036 evidence

This coordination records the pre-preparation finding that amount-only funding
identity rejects legitimate equal-amount top-ups, and that v1 `not_deployed`
operations cannot be promoted to preparation.

The remediation is prospective:

```text
SA-CHAN-001A v1
→ unchanged and descriptive-only

SA-CHAN-001B v2
→ fixture_unexecuted
→ funding_request_hash
→ common prepared-instruction contract
```

Only `SA-CHAN-001B` becomes ready. No execution or deployment gate advances.
