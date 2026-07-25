# Claim-link security contract

## Data classification

| Material | Visibility | Persistence in this kit | Permitted destination |
|---|---|---:|---|
| Claim locator | Public opaque identifier | None | Resolver path only |
| Claim secret | Private claim material | None | Ephemeral client callback only |
| Fragment-free claim URL | Public opaque reference | None | Clipboard or UI |
| Resolver result | Application-defined | None | Calling client |

Locators and secrets are independently generated from at least 32 bytes of a
cryptographically secure random source. Length validation proves the identifier
has a 256-bit representation; it cannot prove that an external producer used a
secure generator. Producers must use `generateOpaqueToken` or an equivalent
CSPRNG.

## Required client order

The first-party entry module must run before analytics, error reporting, tag
managers, session replay, or application rendering:

```text
read location.href
→ validate exact HTTPS origin and /claim/<locator>#<secret>
→ synchronously replace history with /claim/<locator>
→ create ephemeral consume-once session
→ initialize permitted application services
```

If parsing or history replacement fails, processing stops. No resolver request
is permitted. Integrations must not put the raw URL in an exception message.

`ClaimLinkSession.consume` exposes secret bytes to one synchronous callback,
marks the session consumed before invoking it, and zeroizes its internal byte
buffer in `finally`. JavaScript engines can retain copies outside this buffer;
callers must not convert the secret to a string, store it, capture it, or pass it
to telemetry.

## Resolver contract

Only this shape may cross the network boundary:

```json
{
  "method": "GET",
  "url": "https://foundry.pay/claim/<locator>",
  "headers": {
    "accept": "application/json",
    "cache-control": "no-store"
  },
  "referrerPolicy": "no-referrer"
}
```

The production resolver and claim page must additionally emit:

```text
Referrer-Policy: no-referrer
Cache-Control: no-store
```

Recommended browser policy:

```text
Content-Security-Policy:
  default-src 'none';
  script-src 'self';
  connect-src 'self';
  img-src 'self' data:;
  style-src 'self';
  base-uri 'none';
  form-action 'none';
  frame-ancestors 'none'
```

The server must return the same external status, body shape, and comparable
timing envelope for missing, expired, consumed, blocked, and malformed locators.
The reference client collapses every non-success and transport failure to
`claim_unavailable`. Rate limiting and abuse monitoring are server obligations
outside this offline kit.

## Forbidden sinks

The secret or a URL containing it must never enter:

- fetch/request URL, headers, body, cookies, or referrer;
- server logs or persistence;
- analytics, session replay, tag managers, or pixels;
- crash/error reports or breadcrumbs;
- evidence bundles;
- clipboard/share output after consumption;
- browser history after parsing;
- rendered DOM, accessibility labels, or screenshots.

Redaction is defense in depth, not authorization to send secret material to a
sink. Integrations must sanitize at the source and apply the provided redaction
boundary before any logging or evidence serialization.

## Fail-closed conditions

- non-HTTPS, unexpected origin, credentials, query string, wrong path;
- locator or secret below the 256-bit encoded minimum;
- malformed percent encoding or non-base64url material;
- repeated secret consumption;
- resolver transport failure or non-success response;
- inability to remove the fragment immediately.
