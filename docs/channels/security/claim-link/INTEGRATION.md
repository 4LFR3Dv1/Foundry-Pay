# Framework-agnostic integration

The integration boundary is intentionally small:

```typescript
const session = ClaimLinkSession.open(window.location.href, window.history);

const claim = await resolveClaim(session.locator, async (request) => {
  const response = await fetch(request.url, {
    method: request.method,
    headers: request.headers,
    referrerPolicy: request.referrerPolicy,
    cache: "no-store",
    credentials: "omit",
  });
  return { ok: response.ok, json: () => response.json() };
});

session.consume((secretBytes) => {
  // Use only to derive/verify the exact claim operation in client memory.
  // Do not stringify, persist, log, capture, or transmit secretBytes.
});
```

The entry module containing `ClaimLinkSession.open` must execute before
analytics or error instrumentation. Do not catch the parsing error by logging
`window.location.href`; report only the stable error code after redaction.

The example does not define the future claim/binding protocol. It only shows the
security boundary around browser navigation and resolver lookup.
