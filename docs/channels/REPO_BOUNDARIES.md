# Repository boundaries

## Decision

Foundry Channels is a program within the public Foundry-Pay repository, not a
third copy of either kernel. Public channel contracts are namespaced so they can
evolve independently. Private Cloud applications and infrastructure remain in
a separate private repository.

## Solana-Agent public

Validated current structure:

```text
Solana-Agent/
├── solana_agent/        # governed runtime, policy, journals, adapters
├── gateway/             # external execution protocol boundary
├── missions/            # declarative developer missions
├── contracts/           # runtime and mission schemas
├── examples/
├── tests/
├── docs/
└── environment/
```

Recommended evolution:

```text
gateway/capabilities/    # capability descriptors, not Foundry business logic
contracts/capabilities/ # generic capability schemas
tests/channel_gateway/  # conformance against Foundry public vectors
```

Do not add Channel, Claim, voucher issuance, link resolution, or business
reconciliation types to Solana-Agent.

## Foundry-Pay public

Use incremental package growth:

```text
Foundry-Pay/
├── packages/
│   ├── external-execution-protocol/  # exists
│   ├── channel-protocol/              # next public package
│   ├── channel-sdk-python/            # create only after protocol stabilizes
│   ├── channel-sdk-typescript/        # create only after protocol stabilizes
│   ├── voucher-verifier/              # may begin inside channel-protocol
│   ├── reference-authorization/       # evolve from services/authorization
│   ├── reference-reconciliation/      # evolve from services/reconciliation
│   └── reference-ledger/              # create after semantics are frozen
├── programs/
│   └── foundry-channel-vault/         # future, not in FOUNDATIONS-001
├── services/
│   ├── reference-channel-gateway/     # future public, deterministic only
│   ├── fake-executor/                 # current fake executor may be generalized
│   └── failure-lab/                   # exists
├── contracts/
│   └── channel/                       # foundation schemas and vectors
├── examples/
├── tests/
└── docs/
    └── channels/
```

The proposed package list is a target map, not permission to create empty
packages. Start `channel-protocol`; split SDKs and verifiers only when their
release cadence or consumers differ.

## Foundry Pay Cloud private

Recommended private topology:

```text
foundry-pay-platform/
├── apps/
│   ├── consumer/
│   ├── business/
│   ├── developer/
│   └── operations/
├── services/
│   ├── channel-registry/
│   ├── identity-resolver/
│   ├── voucher-relay/
│   ├── settlement-orchestrator/
│   ├── reconciliation-worker/
│   ├── notification-service/
│   └── webhook-service/
├── packages/
│   ├── domain/          # imports public types; does not redefine them
│   ├── database/
│   ├── auth/
│   ├── organizations/
│   ├── policy/
│   ├── sdk/
│   └── observability/
└── infrastructure/
```

The private repository consumes versioned public packages. It must not vendor
or fork their kernels. Customer-specific policy may narrow public operations,
never broaden signed or on-chain authority.

## Coupling and versioning

| Boundary | Compatibility contract |
|---|---|
| Cloud ↔ public protocol | released package version + schema version |
| Foundry ↔ Solana-Agent | capability descriptor + External Execution Protocol |
| protocol ↔ ChannelVault | program version, IDL hash, program ID, account version |
| signer ↔ executor | exact message and execution authorization hashes |
| reconciler ↔ providers | normalized observation schema + source registry |

Breaking changes require a new major protocol version or explicit migration.
Unknown fields are rejected in signed objects.

## Contribution and IP

- All content in the public Foundry-Pay repository is Apache-2.0 where the
  licensor holds the necessary rights.
- Solana-Agent remains its own Apache-2.0 project.
- Private Cloud code, customer configuration, custody, proprietary policy,
  operations, analytics, and SLAs are not published.
- Public schemas, verifier behavior, test vectors, program interfaces, and
  sanitized evidence must remain sufficient for independent integration.

## Local development

The public repository must always support:

- schema/vector validation without Solana toolchain;
- deterministic fake executor and reference-ledger tests;
- local validator program integration when implemented;
- opt-in devnet proof;
- Cloud-free client recovery fixtures.

The private repository may compose these packages but cannot become the only
way to test a right-critical flow.
