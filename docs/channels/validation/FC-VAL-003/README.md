# FC-VAL-003 — 30-second proposition comprehension test

Status: **protocol revision ready for review; recruitment blocked; human
validation not performed**.

This directory defines a preregisterable test of the proposition:

> Abra um canal. Compartilhe um link. Envie quantas vezes quiser.

It does not contain interview claims or participant data. The work item remains
incomplete until the privacy gate is approved, at least five eligible people
complete the tagged protocol, two reviewers score every included response, and
only suppressed aggregate evidence is reviewed.

## Research question

After 30 seconds of exposure, can a target user explain that Foundry Channels is
a funded, reusable transfer relationship—rather than a custodial account, a
single payment link, or a stream of additive vouchers?

Stage A measures spontaneous, unaided proposition comprehension. Stage B comes
after a text that supplies the correct model, so it measures comprehension and
recall after teaching. Stage B cannot establish what the headline communicated.
The gates and conclusions remain separate.

## Required sample

Minimum: five completed, eligible participants. Recommended: six to eight so
one exclusion does not invalidate the run.

Recruit participants who:

- are at least 18 years old;
- have sent or received a stablecoin at least twice in the previous six months;
- have used a self-custody wallet at least once;
- are not employed by, contracted by, or close collaborators of Foundry Pay or
  Solana-Agent;
- have not read the Foundry Channels architecture documents.

The completed sample must include at least:

- two people who have repeatedly sent stablecoins to the same person; and
- two people who have received stablecoins into their own wallet.

Record eligibility as coded private data only. Do not publish employer, exact
location, wallet address, transaction signature, income, balances, or identity.

## Materials

1. [Moderator script](MODERATOR_SCRIPT.md)
2. [Scoring rubric](SCORING.md)
3. [Machine-readable result schema](result-record.schema.json)
4. [Illustrative private-record template](participant-record.template.json)
5. [Pre-recruitment privacy checklist](PRE_RECRUITMENT_CHECKLIST.md)
6. [Run-manifest schema](run-manifest.schema.json)
7. [Run-manifest template](RUN_MANIFEST.template.json)
8. [Sanitized aggregate template](sanitized-results.template.json)
9. [Decision template](DECISION.template.md)

No prototype, live wallet, real claim link, valuable asset, or production
account is required. If examples are shown, they must be synthetic.

## Execution protocol

1. Complete and independently approve every item in the pre-recruitment
   checklist.
2. Merge and tag the reviewed protocol, hash every artifact, and freeze an
   approved immutable run manifest before recruitment starts.
3. Obtain informed consent outside the public repository.
4. Assign a 12-character, cryptographically random, non-sequential ID using
   alphabet `A-HJ-NP-Z2-9`; verify uniqueness within the run.
5. Do not create an identity-to-code map by default. If withdrawal requires
   one, store it separately with narrower access and delete it at the declared
   cutoff.
6. Store contact/consent data separately from coded answers.
7. Confirm eligibility without collecting wallet evidence.
8. Read the neutral introduction in the moderator script.
9. Show only the proposition for exactly 30 seconds.
10. Hide it and ask spontaneous questions without correction or prompting.
11. Lock and hash Stage A before displaying Stage B. Later reviews create
    separate fields and never overwrite the locked record.
12. Show Stage B and ask the taught-model questions.
13. Ask comparison and usefulness questions last.
14. Debrief the participant.
15. Store raw notes/recordings and consent privately.
16. Have a second reviewer independently score every included response and
    adjudicate every disagreement or ambiguity with an audit trail.

Sessions should be individual, moderated, and 12–18 minutes long. Do not mix
participants in a group session because answers contaminate one another.

## Outcome gates

The proposition passes the work-item acceptance gate only when all of these are
true:

- at least five eligible participants complete the same protocol;
- every included participant understands `10 → 25 → 40` as a cumulative total
  of `40`, not additive `75`;
- at least 80% identify that the link/relationship can be reused;
- at least 80% identify that the recipient can receive in their own wallet;
- at least 80% distinguish funded, authorized, settled, and remaining amounts
  after the factual scenario;
- no more than 20% infer that Foundry Pay necessarily owns or custodies the
  funds;
- no participant reveals a real secret or valuable link during the study.

Passing Stage B does not prove the headline communicates the model. Stage A and
Stage B must be reported separately.

## Stop and decision rules

Stop recruitment and escalate when:

- any participant shares a seed phrase, private key, claim secret, or valuable
  claim link;
- the research system cannot keep consent and raw data out of this repository;
- the script or scenario changes after the first included participant;
- three of the first five participants interpret `10 → 25 → 40` as `75`;
- three of the first five infer unavoidable custody by Foundry Pay;
- participant distress or a request to withdraw cannot be handled immediately.

If the script changes, close the current run as a versioned pilot. Do not pool
its results with the revised run.

## Privacy and evidence boundary

Public:

- protocol version, tag, manifest hash, and immutable repository commit;
- safe sample totals and preregistered aggregate gate outcomes;
- non-identifying decision changes;
- decisions and unresolved questions.

Private, access-controlled, and never committed:

- names, handles, email, phone, precise location, employer;
- consent artifacts and identity-to-research-ID mapping;
- recordings, transcripts, verbatim quotes, moderator notes;
- wallet addresses, transactions, balances, screenshots;
- recruitment source when it could re-identify someone.

`result-record.schema.json` standardizes private **pseudonymous coded data**.
Pseudonymization is not anonymization. Completed per-participant instances must
not be published, even when they use random IDs. Only the aggregate template is
a public result format.

## Public small-cell policy

Never publish participant-level exports, segment/demographic cross-tabs,
verbatim quotes, recruitment-source details, free-form rare categories,
timestamps, or combinations that could single out a participant.

The small-cell minimum is `3`. Suppress a category count and percentage when
the cell **or its complement** is below 3. Render it as
`SUPPRESSED_SMALL_CELL`, never zero. Roll rare categories and
`OTHER_ROLLED_UP` into a broader safe category and suppress the roll-up when it
still fails. Exclusion, attrition, and withdrawal reasons use only controlled
categories and the same rule.

For `N=5`, binary counts are generally reconstructable. Publish only the
preregistered gate state (`pass`, `fail`, or `not_evaluated`), never its
numerator, percentage, segment count, or cross-tab. Total eligible completions
may be published. A gate state is a protocol conclusion, not a participant
record.

The public result is evidence only after it references the tagged commit and
immutable run-manifest hash. The blank template proves no interview occurred.

## Current blocker

The canonical work item assigns raw research to `private/product-research`.
No authorized private research repository or storage system is established by
this public task. Therefore this PR can make the protocol reviewable, but cannot
move `FC-VAL-003` to `review` or `done`, recruit participants, or claim human
validation.

After merge, create tag `fc-val-003-protocol-v0.1.0`. Recruitment remains
prohibited until the private checklist and immutable manifest are actually
approved. Results belong in a separate PR.
