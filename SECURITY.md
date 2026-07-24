# Security policy

Foundry Pay is pre-alpha reference software. Do not use it to custody funds,
manage production signing keys, or execute mainnet payments without an
independent security review and production controls.

## Reporting a vulnerability

Do not disclose a suspected vulnerability in a public issue, discussion, pull
request, evidence bundle, or chat transcript.

Use GitHub's private vulnerability reporting feature:

1. open the repository's **Security** tab;
2. select **Advisories**;
3. choose **Report a vulnerability**;
4. include affected commit, reproduction steps, impact, and suggested
   mitigation if known.

If private vulnerability reporting is unavailable, contact the repository owner
privately through their verified GitHub profile and request a secure reporting
channel. Do not send secrets or exploit material before that channel is
confirmed.

## Scope

High-priority reports include:

- authorization or canonicalization bypass;
- signing bytes not bound to the approved execution commitment;
- replay, duplicate economic effect, or unsafe automatic retransmission;
- receipt, evidence, or journal integrity failure;
- secret exposure or unsafe default network behavior;
- provenance or dependency compromise affecting released artifacts.

Public documentation errors and non-sensitive feature requests may use normal
issues.

## Disclosure process

The maintainer will acknowledge a complete report, reproduce it where possible,
assess affected versions, and coordinate a fix and disclosure. No response-time
or remediation-time service level is promised for this pre-alpha public
project.

Security fixes that affect money movement require independent review before
release.
