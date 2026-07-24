# Pre-recruitment privacy and operations gate

Status: **blocked until every required field is completed and independently
approved for the actual run**.

This is an operational checklist, not legal certification. The controller must
align the final notice and rights workflow with the law applicable to the
participants, including current ANPD transparency and data-subject-rights
guidance before recruiting in Brazil:
<https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares>.

Recruitment, scheduling, recording, screening, or collection must not start
until every item below is `approved` in the private system and its non-sensitive
approval identifier is copied into the immutable run manifest.

## Controller and notice

- [ ] Identify the data controller's legal name.
- [ ] Provide a monitored privacy contact and response owner.
- [ ] State the specific research purpose and prohibit incompatible reuse.
- [ ] Enumerate data categories: contact/consent, screening, coded answers,
      optional recording, moderator notes, scoring/audit data, and aggregates.
- [ ] Record the applicable processing basis reviewed for this actual run.
- [ ] Approve the participant privacy notice in the participant's language.
- [ ] Explain recipients/processors and any international transfer.
- [ ] Explain the right to refuse questions, stop without penalty, withdraw,
      and request deletion where applicable.
- [ ] Declare the free withdrawal channel and exact withdrawal cutoff.
- [ ] Explain what anonymous aggregate may remain after that cutoff.

Required private approval fields:

```text
controller_name:
controller_contact:
privacy_notice_id:
processing_basis_review_id:
rights_request_route:
withdrawal_cutoff:
approver_role:
approved_at:
```

## Storage and access

- [ ] Name every processor and storage product.
- [ ] Record storage region/country and approved transfer mechanism if needed.
- [ ] Separate contact/consent data from coded answers.
- [ ] Confirm role-based least-privilege access and list authorized roles.
- [ ] Confirm encryption in transit and at rest.
- [ ] Confirm audit logging for export, deletion, and access changes.
- [ ] Prohibit production wallets, secrets, claim links, and transaction data.
- [ ] Document incident reporting, containment, participant notification
      decision path, and accountable contact.

Required private approval fields:

```text
storage_approval_id:
processors:
storage_locations:
authorized_roles:
encryption_control_id:
incident_response_id:
```

## Retention, deletion, and withdrawal

- [ ] Set exact retention for contact/consent data.
- [ ] Set exact retention for coded answers and scoring audit.
- [ ] Set exact retention for optional recordings and transcripts.
- [ ] Set deletion timing and verification for active storage.
- [ ] Set backup expiry/deletion timing and document restoration handling.
- [ ] Default to no identity-to-code map.
- [ ] If a map is necessary for withdrawal, document purpose, access, encryption,
      and deletion at the declared withdrawal cutoff.
- [ ] Before the cutoff, delete withdrawn participant answers, recordings,
      contact linkage, and code mapping from the research dataset.
- [ ] Retain only a separately governed minimal rights-request record when
      required; it is not research data.
- [ ] After the declared cutoff, explain that already frozen anonymous
      aggregates may remain and cannot be re-associated.

## Compensation and recording

- [ ] State compensation amount, method, eligibility, and tax implications, or
      explicitly record `none`.
- [ ] Ensure compensation is not conditioned on answering every question.
- [ ] Obtain recording consent separately from research consent.
- [ ] Keep recording optional; refusal must not exclude an otherwise eligible
      participant.
- [ ] Provide a non-recorded note-taking path.

## Final go/no-go

- [ ] Research/privacy reviewer approved the completed checklist.
- [ ] Product owner approved the frozen protocol and thresholds.
- [ ] Private storage owner verified access, encryption, retention, and deletion.
- [ ] Immutable run manifest was generated from the tagged protocol and signed
      off before the recruitment start timestamp.
- [ ] A dry run used synthetic answers only and created no personal data.

If any box becomes false, pause recruitment and set the run to
`blocked_privacy`. A checklist stored only in this public repository is not an
approval.
