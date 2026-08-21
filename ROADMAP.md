# Roadmap

Foundry Pay is a pre-alpha public reference implementation for governed economic
execution. The roadmap describes which capabilities the program intends to make
true next and why. It does not authorize work, deployment, mainnet use, custody,
or production claims.

Three public surfaces have different jobs:

| Surface | Question it answers |
| --- | --- |
| `ROADMAP.md` | What capability should become true next, and why? |
| work graphs | What work is currently allowed to begin? |
| evidence indexes | What has actually been demonstrated, at which maturity and environment? |

Detailed execution state belongs to the relevant work graph. Demonstrated
claims belong to [`docs/EVIDENCE.md`](docs/EVIDENCE.md) and the
[Channels evidence index](docs/channels/EVIDENCE_INDEX.md).

The roadmap has no promised dates or service levels.

## Demonstrated baseline

### External Execution

The public reference path has already demonstrated:

- versioned External Execution Protocol objects and deterministic
  canonicalization;
- short-lived, single-use authorization bound to exact prepared message bytes;
- an isolated signing boundary with no business authority;
- one governed SPL transfer on Solana devnet;
- one controlled-runtime broadcast for the demonstrated obligation;
- recovery after ambiguous or lost RPC responses without blind retransmission;
- source-diverse L1/L2 reconciliation of the same finalized transaction;
- deterministic and real-process failure matrices;
- sanitized, hash-bound evidence and reproducible local proofs.

This establishes a governed execution baseline. It does not establish mainnet,
production custody, universal exactly-once blockchain execution, or externally
audited security.

### Foundry Channels

The Channels program has advanced beyond its original architecture foundation.
The current public evidence includes, at the maturity explicitly recorded by
the program:

- executable channel and funding validation;
- cumulative voucher verification and monotonic reference state;
- claim and dual-signature recipient binding;
- settlement, recovery, close, expiry, epoch, and refund reference behavior;
- normative canonicalization and independent Python/TypeScript/Rust
  conformance;
- adversarial replay, semantic-collision, downgrade, and lifecycle tests;
- claim-link secret-handling tests;
- fixed-width ChannelVault account and instruction contracts;
- transition invariants, bounded state exploration, and concurrency models;
- upgrade, migration, rights-preservation, and governance models;
- transport-independent capability contracts and Solana-Agent channel
  operation/preparation boundaries through `SA-CHAN-001B`.

These are protocol, model, fixture, and integration proofs. No operational
ChannelVault program, signer-backed channel execution, live channel funding,
devnet channel settlement, or mainnet deployment is claimed.

## Now — make the public system externally legible and verifiable

The highest-value next step is not simply more internal implementation. It is
to prove that people outside the authoring loop can understand, reproduce, and
challenge the system.

### External developer verification

The public onboarding path should support an independent developer who can:

1. clone the repository from a clean environment;
2. run the deterministic local proof and documented protocol suites;
3. inspect the committed evidence and the public devnet transaction;
4. reproduce key hashes, recovery behavior, or conformance results;
5. publish a substantive issue, report, integration, or independent evidence
   record.

Success means the project has external technical verification that is distinct
from self-validation.

### Human product comprehension

The first Channels proposition remains deliberately simple:

> Open a channel. Share a link. Send as often as you want.

Before expanding the consumer implementation, the program should execute the
ready comprehension gate (`FC-VAL-003`) and test whether people can correctly
explain:

- funded versus sent versus still available value;
- why cumulative `10 -> 25 -> 40` means a total entitlement of `40`, not `75`;
- how a recipient binds the intended destination wallet;
- why an ambiguous network result enters recovery instead of triggering a
  second payment attempt;
- what can be independently verified without trusting a hosted service.

Product UI work should follow evidence of comprehension rather than substitute
for it.

### External Execution protocol stabilization

In parallel, the existing execution boundary should become easier for other
implementers to consume. Directional stabilization includes:

- closed errors, capabilities, and version negotiation;
- correlated journal and evidence-manifest contracts;
- simulation validity, expiry, and drift handling;
- package-level quickstarts;
- executor conformance tooling and portable verification.

These are interoperability and usability improvements to an already-demonstrated
execution path, not prerequisites for beginning human validation.

## Next — complete the Channels execution-preparation boundary

The immediate technical frontier for Channels is the capability-specific
Solana-Agent preparation path already released by the Channels work graph.

The intended progression is:

```text
SA-CHAN-002  initialize / funding / activation preparation
        \
         +--> SA-CHAN-003A  binding / close / refund / finalization preparation
        /
SA-CHAN-003  settlement preparation
                 |
                 v
          SA-CHAN-004  inspect / status / recovery
                 |
                 v
          SA-CHAN-005  evidence / conformance
```

`FC-FAIL-003` remains a parallel offline failure-validation lane where useful.

The completion condition for this stage is not "ChannelVault is live." It is:

> Every required channel operation has a closed, versioned preparation,
> correlation, status, recovery, and evidence boundary sufficient for a later
> authority decision about real execution.

Handlers, signer access, RPC execution, local-validator execution, devnet,
mainnet, and real assets remain separately governed capabilities.

## Later — authorize and prove the first real ChannelVault vertical slice

The current Channels foundation explicitly does not authorize an operational
Solana program. Moving from a complete model to a real program therefore
requires a new explicit governance decision rather than an implicit continuation
of offline work.

The transition should be treated as a capability gate:

```text
protocol and model evidence
        |
        v
explicit implementation authorization
        |
        v
ChannelVault program implementation
        |
        v
local-validator proof
        |
        v
explicit devnet authorization
        |
        v
end-to-end devnet channel proof
```

The target devnet proof should exercise the product thesis end to end:

```text
fund fixture channel
-> issue and activate cumulative value
-> open protected claim
-> bind destination wallet
-> settle through exact authorization
-> recover an intentionally ambiguous response
-> reconcile independently
-> close / preserve rights / refund eligible capacity
-> publish reproducible evidence
```

A successful devnet proof still does not imply mainnet or production readiness.

## Later — prove that Foundry Pay is not chain-specific

The architecture is intended to separate economic authority from
network-specific execution. A second independently implemented blockchain
execution environment is therefore an architectural proof, not merely another
integration.

The desired shape is:

```text
                         Foundry Pay
                    economic authority
                           |
                 exact authorization
                     /             \
                    v               v
             Solana executor    EVM executor
                    |               |
                 Solana          EVM network
```

A second environment should reproduce the same essential guarantees:

- bounded economic intent;
- exact execution authorization;
- constrained signer authority;
- durable ambiguous-outcome recovery;
- independent economic reconciliation;
- portable evidence.

Celo is a candidate for the first EVM execution environment because its
stablecoin and agent-payment surface aligns with this proof. It remains a
candidate lane until an explicit work item and authority decision activate it.
The architectural requirement is more important than the particular network:
Foundry Pay must remain the economic authority while the executor remains a
replaceable network specialist.

## Later — convert validated protocol primitives into product surfaces

Consumer work should unlock behind the validation and execution boundaries,
not race ahead of them. The intended product sequence remains:

```text
comprehension evidence
-> receive / protected-claim prototype
-> destination onboarding
-> persistent-channel experience
-> settlement and recovery UX
-> receipts and sharing
-> repeated-use validation
```

A product claim requires evidence that people understand and reuse the
primitive, not only that the protocol can represent it.

## Production gates

Production is not one milestone. Security maturity, operational maturity, and
market validation remain independent requirements.

| Frontier | Required evidence before a production claim |
| --- | --- |
| Security | exact-version external security review; hardened signer/custody boundary; adversarial review of deployed artifacts |
| Operations | sustained runtime observation; incident and recovery practice; observability; upgrade and migration procedures |
| Reconciliation | L3 or equivalent independent observation where appropriate; explicit disagreement and dispute handling |
| Release engineering | versioning, migrations, support policy, reproducible releases, and artifact provenance |
| Mainnet authority | explicit mainnet-readiness review and explicit operational authorization for exact artifacts |
| Product | independent users, external integrations, comprehension, repeated use, and evidence of real demand |

No item above can be inferred from implementation completeness alone.

The maturity model remains:

```text
work item delivered
!= self-validation passed
!= external review passed
!= deployment authorized
!= production ready
```

## Directional priority

Until new evidence changes the decision, the program priority is:

```text
external verification + human validation
-> complete Channels execution boundaries
-> explicitly authorize real ChannelVault execution
-> prove the devnet vertical slice
-> prove a second network execution environment
-> pursue production gates only with independent evidence
```

The roadmap should change when evidence changes the decision. The work graphs
should change when authority changes. Neither should be advanced merely because
more code can be written.
