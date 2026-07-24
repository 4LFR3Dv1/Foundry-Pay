# Public and commercial boundary

Foundry Pay publishes an Apache-2.0 reference implementation for governed
stablecoin reconciliation and controlled remediation. The open protocol is the
shared interoperability layer. A production service may add operational
capabilities around it without changing what the public repository licenses.

## Included in the public repository

| Surface | Purpose |
|---|---|
| External Execution Protocol | Versioned contracts between economic authority and network executors |
| Canonicalization and schemas | Deterministic objects, hashes, validation, and exact-message binding |
| Reference authorization and signer | Demonstrate short-lived, single-use authorization and exact-byte signing |
| Reference reconciliation | Demonstrate source-diverse observation and deterministic outcomes |
| Fake executor and conformance vectors | Permit local integration without wallets, RPC access, or funds |
| Failure and recovery labs | Demonstrate ambiguous-outcome handling and duplicate-effect prevention |
| Sanitized evidence | Make completed technical claims independently inspectable |

These surfaces are open source under Apache-2.0 when Foundry Pay holds the
necessary rights. Third-party materials retain their respective licenses and
notices.

## Outside the public repository

| Surface | Reason |
|---|---|
| Production credentials and customer data | Secret and privacy boundary |
| Custody, HSM, MPC, and production key management | High-assurance operational boundary |
| Customer deployments and tenant configuration | Customer-specific infrastructure |
| Private risk rules and proprietary connectors | Commercial integration layer |
| Managed monitoring, incident response, and compliance operations | Operated service |
| Support commitments and service-level agreements | Commercial relationship |

This list describes absent and separable capabilities. It does not narrow the
rights granted by Apache-2.0 for code already published in this repository.

## Authority boundary

Foundry Pay owns economic intent, global policy, approval, execution
authorization, reconciliation, and the final business result. An external
executor owns network-specific preparation, simulation, execution,
confirmation, recovery, and technical receipts.

Neither a hosted offering nor an external executor may broaden an authorization
created by the economic authority. Free-form prompts never cross the execution
boundary, and an unknown broadcast outcome never permits automatic
retransmission.

## Contribution boundary

Contributions are welcome for the public protocol, reference implementations,
tests, documentation, sanitized fixtures, and developer tooling. Do not submit:

- production keys, tokens, credentials, wallet material, or customer data;
- deployment topology or non-public security configuration;
- code or fixtures whose ownership or license cannot be demonstrated;
- private integrations contributed without authorization from their owner.

See `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `NOTICE`, and
`provenance/THIRD_PARTY_NOTICES.md`.
