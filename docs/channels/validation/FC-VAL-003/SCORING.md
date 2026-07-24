# Scoring rubric

Score from the participant's answer before any correction. Two reviewers should
resolve ambiguous cases. Preserve only category codes in public evidence.

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
