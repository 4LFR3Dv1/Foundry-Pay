# FC-PROTO-004 evidence

Offline settlement, technical execution correlation, recovery, and independent
economic reconciliation reference runtime.

## Immutable references

- baseline: `b20fa0203089eff242998e47485377921b1c10b4`
- implementation: `79fc80c37e973457b8f23422b4e18b7d0deeec47`
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

- focused settlement cases: 47 passed;
- full pytest: 330 passed, 11 expected skips,
  0 failures, 0 errors;
- external execution TypeScript: 8 passed;
- channel protocol TypeScript: 18 passed;
- npm audit: zero high-severity vulnerabilities in both packages;
- secret guard: 261 files passed.

## Claim boundary

The evidence supports only at-most-one submission attempt by the controlled
offline reference runtime in the tested model. Recovery is correlated to the
committed executor and exact status-response hash. Economic completion requires
an injected source-specific observation verifier; a self-asserted source ID is
insufficient. Disputed settlements retain their reservation. This does not
prove exactly-once blockchain execution, Solana execution, ChannelVault
behavior, on-chain origin of snapshots or observations, Cloud behavior,
consumer demand, or production readiness.
