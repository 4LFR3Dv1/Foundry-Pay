# FC-GOV-001 evidence

This pack records the program-wide change from a merge-implies-review model to
independent, version-bound records for implementation, self-validation,
external review, and deployment authorization.

## Demonstrated

- `done` remains a work-item execution state and does not imply audit;
- passed and stale validation/review states retain immutable commit evidence;
- allowed authorizations bind the current commit and a decision reference;
- local and fixture experimentation require current self-validation;
- mainnet and real-value authorization require passed exact-version external
  review and closed operational constraints;
- FC-PROTO-007 is explicitly recorded as externally unreviewed;
- ChannelVault, devnet, mainnet, and real-value execution remain unauthorized;
- the policy is program-wide and is integrated before PR #34 can change its
  review gate.

## Not demonstrated

- an external review of FC-PROTO-007;
- ChannelVault implementation or security;
- a devnet deployment;
- mainnet or real-value safety;
- production authorization.

Run:

```text
python scripts/check_maturity_authorization.py contracts/governance/examples/fc-proto-007-self-validated.json
python -m pytest tests/channels/test_maturity_authorization.py
```
