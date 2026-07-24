# Scoring rubric

This rubric is frozen for `fc-val-003-v1`. Score from the participant's answer
before any correction. Every included response is independently scored by two
reviewers. Preserve category codes—not participant records—in public evidence.

## Stage A

Each dimension is `0`, `1`, or `2`:

- `0`: absent or materially incorrect;
- `1`: partial, uncertain, or correct only after a neutral probe;
- `2`: clear and spontaneous.

| Code | Dimension | Score 2 | Score 1 | Score 0 |
|---|---|---|---|---|
| A1 | persistent relationship | reusable relationship/channel | hints at repeated use | assumes one-off payment |
| A2 | reusable link | same link works again | uncertain reuse | link expires after first transfer |
| A3 | repeated-address benefit | no repeated wallet-address request | mentions convenience only | no distinction from ordinary transfer |
| A4 | recipient destination | recipient's own wallet/destination | wallet mentioned ambiguously | Foundry account is necessarily destination |
| A5 | custody uncertainty | explicitly asks/does not assume custody | uncertain controller | confidently assumes Foundry custody |
| A6 | proposition clarity | accurate explanation without invented behavior | main action understood | wrong product category |

Report Stage A total out of 12, plus each dimension. Do not use only the total;
a high total cannot hide custody or one-off-link misconceptions.

A Stage A dimension passes only when its final adjudicated score is exactly
`2`. A score of `1` is analytically useful but does not pass. A participant is
an `M01_ONE_OFF_LINK` case only when the answer explicitly describes a one-use
link and final `A1=0` and `A2=0`. A participant is an
`M03_CLOUD_CUSTODY_REQUIRED` case when the answer explicitly says Foundry must
hold/control the funds; final `A5=0` must also be assigned. These mappings
cannot be redefined after recruitment begins.

## Stage B

Score each as pass/fail:

| Code | Required answer |
|---|---|
| B1 | final authorized total is 40, not 75 |
| B2 | after 15 settled, 25 remains liquidatable |
| B3 | after 40 settled from 100, 60 remains funded |
| B4 | funded, authorized, settled, and remaining are distinguished |
| B5 | old voucher is non-additive |
| B6 | Cloud cannot fabricate sender authorization |
| B7 | protected claim link is sensitive and should not be forwarded |
| B8 | unknown result triggers status/recovery, never blind retry |
| B9 | signature issues; program acceptance activates the liquidatable right |
| B10 | closing preserves a presentation window for a previously signed voucher |

`B4` passes only when the participant correctly describes all four terms.

Stage B follows an explanation that supplies the correct model. It measures
comprehension and recall **after teaching**, not unaided headline
comprehension. Stage B success must never be used to convert a Stage A failure
into a headline success.

## Misconception codes

Use any that apply:

- `M01_ONE_OFF_LINK`
- `M02_ADDITIVE_10_25_40`
- `M03_CLOUD_CUSTODY_REQUIRED`
- `M04_CLOUD_CAN_AUTHORIZE`
- `M05_RECIPIENT_NEEDS_FOUNDRY_WALLET`
- `M06_LINK_SAFE_TO_FORWARD`
- `M07_UNKNOWN_RESULT_RETRY`
- `M08_STREAMING_ASSUMPTION`
- `M09_UNFUNDED_CREDIT_ASSUMPTION`
- `M10_NO_EXPIRY_OR_CLOSE_RULES`
- `M11_ISSUED_EQUALS_ACTIVATED`
- `M12_CLOSE_IMMEDIATE_REVOCATION`

Use `OTHER_SANITIZED` with a non-identifying paraphrase category when needed.

## Aggregate decisions

Use the gates in `README.md`, not post-hoc thresholds. Outcomes:

- `pass`: every mandatory gate passes;
- `revise_message`: Stage A misses a gate but Stage B accounting is understood;
- `revise_model_explanation`: Stage B accounting/safety misses a gate;
- `stop_and_review`: custody or additive interpretation reaches the stop rule;
- `insufficient_sample`: fewer than five eligible completions;
- `blocked_privacy`: approved private research storage/review is unavailable.

Never delete an excluded or failed run to improve the result. Report counts and
exclusion reasons without identifiers.

## Denominators and thresholds

`N` is the number of eligible, completed records with `final_adjudicated`
scoring. Ineligible, incomplete, withdrawn, pilot, protocol-deviation, or
unadjudicated records are excluded from metric denominators and reported only
under safe attrition rules.

Use integer thresholds; do not round a percentage to make a gate pass:

```text
required_80 = ceil(0.80 × N)
maximum_20 = floor(0.20 × N)
```

| N | required_80 | maximum_20 |
|---:|---:|---:|
| 5 | 4 | 1 |
| 6 | 5 | 1 |
| 7 | 6 | 1 |
| 8 | 7 | 1 |

- Stage A `A1`, `A2`, `A3`, and `A4`: at least `required_80` score `2`.
- Stage A custody: `M03` count no greater than `maximum_20`.
- Stage B `B1`: all `N` must pass.
- Stage B `B2`–`B10`: each requires at least `required_80`.
- Minimum sample/segment requirements are gates, not metric denominators.

Internal percentages may be calculated as `count / N × 100` and rounded to one
decimal using round-half-up. Public small-sample output follows the suppression
rules in `README.md` and may publish only gate status, not reconstructable
counts or percentages.

## Independent scoring and audit

1. The moderator/primary scorer records and locks Stage A before revealing
   Stage B. The locked record receives a SHA-256 hash.
2. Stage B is stored separately. Neither stage overwrites the other.
3. A second reviewer independently scores **every** included response without
   seeing the primary scores.
4. A response is ambiguous when it supports two conflicting rubric outcomes,
   lacks enough context to choose a score without inference, or a neutral probe
   changed its substantive meaning.
5. Any primary/secondary difference or either reviewer's ambiguity flag
   requires adjudication by a named research role using the frozen rubric.
6. Store primary, secondary, and adjudicated scores separately. Never replace
   the earlier scores.
7. Record disagreement, ambiguity, and adjudication counts plus an opaque
   private audit reference. The audit trail remains pseudonymous private data.

If the rubric mapping changes, increment the protocol version and start a
separate pilot/run. Never pool results across versions.
