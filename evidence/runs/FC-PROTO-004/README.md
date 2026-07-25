# FC-PROTO-004 evidence

Offline settlement, technical execution correlation, recovery, and independent
economic reconciliation reference runtime.

## Immutable references

- baseline: `b20fa0203089eff242998e47485377921b1c10b4`
- implementation: `369c52527cfd4b3d4603a9ab4dd36df822db350f`
- reviewed head: assigned only after the evidence commit is independently reviewed

## Reproduction

```text
python -m pytest tests/channels/test_settlement.py -q
python -m pytest -q --junitxml evidence/runs/FC-PROTO-004/pytest-full.xml
python scripts/check_channel_foundation.py
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
npm test --prefix packages/external-execution-protocol/typescript
npm test --prefix packages/channel-protocol/typescript
```

## Result

- focused settlement cases: 43 passed;
- full pytest: 326 passed, 11 expected skips,
  0 failures, 0 errors;
- external execution TypeScript: 8 passed;
- channel protocol TypeScript: 18 passed;
- npm audit: zero high-severity vulnerabilities in both packages;
- secret guard: 262 files passed.

## Claim boundary

The evidence supports only at-most-one submission attempt by the controlled
offline reference runtime in the tested model. It does not prove exactly-once
blockchain execution, Solana execution, ChannelVault behavior, on-chain origin
of snapshots or observations, Cloud behavior, consumer demand, or production
readiness.
