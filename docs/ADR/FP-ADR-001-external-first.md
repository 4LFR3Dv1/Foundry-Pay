# FP-ADR-001: External-first execution in two phases

- Status: Accepted
- Decision date: 2026-07-23
- Owners: Foundry Pay architecture

## Context

Foundry Pay needs network-specific execution while retaining deterministic
economic authority. Solana-Agent already has specialized Solana knowledge and a
public-good identity. Absorbing its kernel would couple products, duplicate
runtime evolution, and mix global authority with local execution.

Economic approval alone is insufficient because the concrete transaction
message does not yet exist when the business effect is approved.

## Decision

Foundry Pay adopts an external-first, protocol-first architecture.

The protocol has two phases:

```text
PREPARE
EconomicPlan -> EconomicApproval -> external preparation
  -> local policy -> materialized message -> simulation -> commitment

COMMIT
Foundry verification -> ExecutionAuthorization -> signer
  -> broadcast -> confirmation -> independent reconciliation -> evidence
```

Foundry Pay controls economic intent, global policy, economic approval,
execution authorization, reconciliation, and the final business result.

Solana-Agent remains an independent external executor. It controls local Solana
safety, preparation, simulation, transmission, technical confirmation,
recovery, and technical receipts.

The signer is a third boundary and signs only the exact message whose bytes are
covered by a valid, short-lived, single-use authorization.

## Normative commitments

- `economic_plan_hash = SHA-256(JCS(normalized_economic_plan))`
- `prepared_message_hash = SHA-256(serialized_transaction_message_bytes)`
- `execution_commitment_hash` binds the economic plan, exact message,
  simulation, executor identity/version, constraints, and expiry.
- Any changed message byte requires a new preparation, simulation, commitment,
  and authorization.
- Unknown broadcast state is recovered by status lookup and independent chain
  observation; it is not retried automatically.
- No local policy can override a global block.

## Consequences

Positive:

- preserves independent product and public-good boundaries;
- supports other executors without changing economic authority;
- makes exact authorization and recovery testable;
- creates a reusable open conformance protocol.

Costs:

- distributed journals and correlation;
- protocol versioning;
- failure recovery and ambiguity states;
- explicit signer and reconciliation boundaries.

## Rejected alternatives

- Extract the Solana-Agent kernel into Foundry Pay.
- Send free-form prompts to the executor.
- Approve only an economic effect and allow the executor to choose final bytes.
- Retry automatically after an unknown broadcast result.
