# External Verification Contract

This document defines the authority and evidence boundary for `FP-VER-001`, the
first independent external developer verification of the public Foundry Pay
baseline.

The purpose is not to obtain a friendly testimonial. The purpose is to learn
whether a developer outside the authoring loop can independently reproduce,
inspect, and challenge the public evidence from a clean environment.

## Authority boundary

`FP-VER-001` may be activated only after all of the following are true:

1. an immutable Foundry Pay baseline commit is recorded;
2. the verifier is identified and satisfies the independence rule below;
3. the verifier accepts the public verification protocol and disclosure
   boundary;
4. the exact verification scope is recorded before the run begins.

A `ready` work item authorizes this bounded activation process. It does not let
an internal author self-attest an external result, alter the target artifacts,
or broaden deployment authority.

The top-level work graph remains the authority for readiness and ownership.
`docs/EVIDENCE.md` remains the authority for demonstrated claims.

## Independence rule

A qualifying verifier must be outside the authoring loop for the baseline being
verified. At minimum, the verifier must not have authored, merged, or been the
sole reviewer of the target work items or evidence artifacts.

The verification record must disclose enough relationship information to make
the independence claim reviewable. A public GitHub identity is sufficient; no
private personal information is required.

Project maintainers may answer onboarding questions, but they may not:

- operate the verifier's environment;
- choose or edit the verifier's observed results after the run starts;
- supply unpublished expected outputs as computation input;
- suppress a reproducible failure or disagreement;
- author the verifier's final report and present it as independent work.

If the verifier materially contributed to the target baseline, stop and select
a different baseline or verifier.

## Baseline and environment

The verifier must start from a clean clone of the exact recorded baseline, not
from an unpinned moving `main` branch.

The public verification path must not require:

- private keys or seed phrases;
- production credentials;
- paid infrastructure;
- custody access;
- a funded wallet;
- private customer or operator data.

A verifier may use an independently selected public RPC or explorer when
checking public devnet observations. Credential-bearing endpoints must not be
published.

## Required verification path

A conforming run performs all of the following against the immutable baseline:

1. clone the repository into a clean environment and record OS/runtime/tool
   versions;
2. install dependencies from the documented public setup;
3. run `python examples/local_proof.py`;
4. run the documented External Execution protocol tests;
5. run at least one documented Foundry Channels protocol or conformance suite;
6. inspect the committed External Execution evidence and the canonical public
   Solana devnet transaction;
7. independently reproduce at least one material committed hash, invariant, or
   deterministic result without copying the expected value into the
   computation;
8. challenge at least one recovery, tamper-rejection, replay, or cross-language
   conformance behavior;
9. publish the exact commands, observed results, deviations, and conclusion.

A failure to reproduce is a valid observation and must be preserved.

## Minimum command set

The baseline documentation may add commands, but a first run should include at
least:

```text
python -m pip install -e ".[dev]"
python examples/local_proof.py
python -m pytest
npm ci --prefix packages/external-execution-protocol/typescript
npm test --prefix packages/external-execution-protocol/typescript
npm ci --prefix packages/channel-protocol/typescript
npm test --prefix packages/channel-protocol/typescript
```

A verifier may narrow a failing command after first recording the complete
failure.

## Verification record

The external report must contain:

- verifier identity or stable public handle;
- relationship / independence disclosure;
- exact Foundry Pay commit;
- date and environment description;
- commands executed;
- pass/fail/skip result for each required step;
- independently recomputed material value and method;
- adversarial or recovery/conformance challenge performed;
- discrepancies and unresolved questions;
- links to any issue, fork, patch, or independent evidence;
- one final conclusion from the vocabulary below.

The preferred public form is a GitHub issue, a report in an independent fork,
or a pull request authored by the verifier. Maintainers may later index the
result in `docs/EVIDENCE.md`, but must preserve the original external record.

## Conclusion vocabulary

A valid external run ends in exactly one of these conclusions:

- `reproduced`: the required public claims reproduced within the declared
  baseline and scope, with no material unresolved discrepancy;
- `reproduced_with_findings`: the core claim reproduced, but the verifier found
  material documentation, portability, robustness, or correctness findings
  that must remain visible;
- `not_reproduced`: one or more material required claims did not reproduce;
- `invalid_run`: the run cannot support an external conclusion because the
  baseline, independence, environment, or evidence record was not valid.

`not_reproduced` is not converted to `invalid_run` merely because the result is
unfavorable.

## Work-item completion versus technical conclusion

`FP-VER-001` delivery and the verifier's technical conclusion are separate
facts.

A valid independent report can complete the work item even when its conclusion
is `not_reproduced`. In that case, the repository may claim that external
verification was attempted and found a reproducible gap; it may not claim the
baseline was externally reproduced.

Only `reproduced` or `reproduced_with_findings` can support the narrower claim
that the exact baseline received independent external developer reproduction.

## What this does not authorize or prove

External developer verification is not equivalent to:

- a professional security audit;
- formal verification;
- an external security review of every component;
- deployment authorization;
- mainnet readiness;
- production custody or signer safety;
- an SLA or operational-readiness assessment;
- product-market fit or human product validation.

No mainnet, real-value, custody, production, ChannelVault deployment, or second
network authority is created by `FP-VER-001`.

## Stop conditions

Stop the run and record the reason when:

- a secret or credential would need to be disclosed;
- the verifier is not independent of the target baseline;
- the baseline changes after the run begins;
- a required result can be produced only by using the committed expected output
  as computation input;
- the target evidence cannot be located or its provenance cannot be resolved;
- a maintainer would need to operate the verifier's environment to obtain the
  result;
- the requested action would require mainnet, real value, custody, or production
  access.
