# FC-SEC-003 — Claim-link security kit

Status: reference security primitive, offline only.

This kit defines the narrow client boundary for links shaped as:

```text
https://foundry.pay/claim/<locator>#<secret>
```

The `locator` is a 256-bit opaque routing identifier and may be sent to the
resolver. The `secret` is 256-bit private claim material and remains in the URL
fragment and client memory. Browsers exclude fragments from HTTP requests, but
that browser property alone is insufficient: frontend code can still leak the
fragment through telemetry, exceptions, copy actions, DOM content, or third
party scripts.

The reference TypeScript package therefore provides:

- exact origin/path/locator/secret validation;
- browser-safe base64url processing through Web APIs and `Uint8Array`, with no
  Node runtime dependency;
- immediate `history.replaceState` removal of the fragment;
- an ephemeral consume-once secret session with best-effort byte zeroization;
- locator-only resolver requests with `referrerPolicy: "no-referrer"`;
- uniform public resolution errors;
- recursive redaction for strings, nested values, errors, encoded fragments,
  telemetry, and evidence;
- safe fragment-free sharing output;
- injected local transport tests that exercise browser HTTP semantics without
  network access.

Raw parsing is intentionally private to the module. The public API cannot
return secret bytes without successful synchronous fragment removal and the
consume-once session boundary.

The kit does not:

- persist a locator or secret;
- contact a Cloud service itself;
- create, sign, verify, activate, or settle a claim;
- assert human identity or wallet ownership;
- implement a consumer UI;
- make the Cloud authoritative over recipient binding or economic rights.

## Commands

```text
npm ci --prefix packages/channel-protocol/typescript
npm test --prefix packages/channel-protocol/typescript
```

All fixtures are synthetic. Mandatory frontend security review remains a gate
before the primitive is embedded in a browser application.
