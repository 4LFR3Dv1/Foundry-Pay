# Foundry Channels security gates

- Register version: 1
- Recorded: 2026-07-24
- Scope: sanitized release gates
- Detailed local review: not a public artifact
- Independent external security review: **not performed**

This register intentionally records severity, status, and blocked surfaces
without publishing exploit procedures, credentials, customer data, custody
configuration, or operational secrets.

```yaml
frontend_compromise:
  severity: critical
  status: open
  must_be_resolved_by: FC-SEC-003
  blocks:
    - consumer claim deployment
    - any flow where browser code can access claim private material
  minimum_gate:
    - fragment non-disclosure tests
    - CSP and dependency controls
    - wallet-native destination confirmation
    - independent review of claim-key lifecycle

operational_signer_compromise:
  severity: critical
  status: open
  blocks:
    - delegated signing
    - live channel settlement with meaningful value
  minimum_gate:
    - operated custody architecture
    - exact-byte and short-lived authorization enforcement
    - key rotation and incident recovery
    - independent security review

channelvault_upgrade_compromise:
  severity: critical
  status: open
  must_be_resolved_by: FC-SOL-005
  blocks:
    - program deployment beyond controlled devnet fixtures
    - mainnet
  minimum_gate:
    - reproducible verified build
    - explicit upgrade authority policy
    - multisig and timelock or immutability decision
    - migration and rollback analysis

independent_external_security_review:
  status: not_performed
  blocks:
    - production claim
    - mainnet claim
    - safe-custody claim
```

These gates do not block `FC-PROTO-001`, `FC-PROTO-002`, or
`FC-PROTO-003` as offline reference implementations with no wallet, RPC, Cloud,
signer, or program dependency. They become blocking when work crosses into
money-moving or secret-bearing surfaces.

The full design-threat taxonomy remains in [THREAT_MODEL.md](THREAT_MODEL.md).
No entry in this register represents a claim that an external audit,
production operation, mainnet readiness, or secure custody has been completed.
