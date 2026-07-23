# Architecture

```text
OperationalIntent
  -> ContextSnapshot
  -> EconomicPlan
  -> GlobalPolicyDecision
  -> EconomicApproval
  -> ExternalExecutionRequest
  -> PreparedExecution
  -> LocalPolicyDecision
  -> SimulationAttestation
  -> ExecutionCommitment
  -> ExecutionAuthorization
  -> SignerAttestation
  -> ExternalExecutionReceipt
  -> ReconciliationResult
  -> EvidenceBundle
```

## Authority boundaries

| Boundary | Authority |
|---|---|
| Foundry Pay | economic intent, global policy, approval, authorization, reconciliation, final result |
| External executor | local policy, preparation, simulation, broadcast, confirmation, recovery |
| Signer | validate commitment and sign only the exact authorized message |
| Reconciler | observe chain independently and compare execution with the internal obligation |

## Distributed guarantee

The system promises repeatable delivery, idempotent effect where the rail
supports it, and consultable recovery. It does not claim distributed
`exactly once`.
