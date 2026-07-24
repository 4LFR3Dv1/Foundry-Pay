# FC-VAL-003 — 30-second proposition comprehension test

Status: **protocol ready; human validation not performed**.

This directory defines a reproducible test of the proposition:

> Abra um canal. Compartilhe um link. Envie quantas vezes quiser.

It does not contain interview claims or participant data. The work item remains
incomplete until at least five eligible people complete the protocol and a
research privacy reviewer approves the sanitized evidence.

## Research question

After 30 seconds of exposure, can a target user explain that Foundry Channels is
a funded, reusable transfer relationship—rather than a custodial account, a
single payment link, or a stream of additive vouchers?

The test separately measures spontaneous comprehension and comprehension after
a minimal factual explanation. This prevents the explanation from being
mistaken for what the headline communicated on its own.

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

Record eligibility as booleans only. Do not publish employer, exact location,
wallet address, transaction signature, income, balances, or identity.

## Materials

1. [Moderator script](MODERATOR_SCRIPT.md)
2. [Scoring rubric](SCORING.md)
3. [Machine-readable result schema](result-record.schema.json)
4. [Blank private result record](participant-record.template.json)
5. [Sanitized aggregate template](sanitized-results.template.json)
6. [Decision template](DECISION.template.md)

No prototype, live wallet, real claim link, valuable asset, or production
account is required. If examples are shown, they must be synthetic.

## Execution protocol

1. Obtain informed consent outside the public repository.
2. Assign a random research ID such as `P01`; keep its identity mapping in the
   authorized private research system.
3. Confirm eligibility without collecting wallet evidence.
4. Read the neutral introduction in the moderator script.
5. Show only the proposition for exactly 30 seconds.
6. Hide it and ask the spontaneous questions without correction or prompting.
7. Lock the Stage A scores before displaying the factual scenario.
8. Show the Stage B scenario and ask the accounting and safety questions.
9. Ask the comparison and usefulness questions last.
10. Debrief the participant and reiterate that no financial product was used.
11. Store raw notes/recordings and consent privately; export only the allowed
    sanitized fields.
12. Have a second reviewer independently score any ambiguous answer.

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

- protocol version and immutable repository commit;
- inclusion/exclusion counts;
- aggregate scores and category counts;
- sanitized paraphrase categories;
- decisions and unresolved questions.

Private, access-controlled, and never committed:

- names, handles, email, phone, precise location, employer;
- consent artifacts and identity-to-research-ID mapping;
- recordings, transcripts, verbatim quotes, moderator notes;
- wallet addresses, transactions, balances, screenshots;
- recruitment source when it could re-identify someone.

`result-record.schema.json` standardizes the minimum private, coded record. Its
completed per-participant instances must not be published, even when they use
random research IDs. Only the aggregate template is a public result format.

The public result file is evidence of a research run only after it references
the reviewed commit and reports actual counts. The blank template is not
evidence that interviews occurred.

## Current blocker

The canonical work item assigns raw research to `private/product-research`.
No authorized private research repository or storage system is established by
this public task. Therefore this PR can make the protocol reviewable, but cannot
move `FC-VAL-003` to `review` or `done`, recruit participants, or claim human
validation.
