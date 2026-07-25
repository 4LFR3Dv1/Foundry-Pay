# Claim-link threat model

| Threat | Preventive control | Detection | Recovery | Residual risk |
|---|---|---|---|---|
| Server observes secret | URL fragment plus locator-only request builder | Fake-transport wire assertions | Stop request; rotate/revoke claim outside kit | Compromised frontend can exfiltrate before stripping |
| Browser history retains secret | Synchronous `replaceState` on open | History adapter test | Stop if replacement fails | Browser/extension may have observed initial navigation |
| Analytics/crash leak | Initialize only after stripping; recursive redaction | Nested/Error/encoded fixture tests | Disable sink and rotate/revoke claim | Third-party script executing earlier defeats control |
| Referrer leak | `no-referrer` request and response contract | Request fixture assertion | Block deployment missing header | Platform/webview policy bugs |
| Clipboard leak | Only `safeClaimUrl(locator)` may be shared | Clipboard-output test | Clear clipboard guidance | User may copy original address before client runs |
| Locator enumeration | 256-bit CSPRNG identifier; uniform errors | Size/generation and error-equivalence tests | Rate limit/monitor in resolver | Timing and operational metadata require live review |
| Repeated client consumption | State flips before callback; buffer zeroized | Double-consume and retained-buffer tests | Require new authorized flow | Multiple tabs/devices are authoritative protocol concerns |
| Encoded secret evades sanitizer | Raw, URL, percent and double-percent redaction | Encoded fixture tests | Rotate/revoke and purge sink | Arbitrary transformations cannot all be recognized |
| Malicious origin/path substitution | Exact HTTPS origin and path grammar | Negative parser suite | Reject locally | DNS/TLS/platform compromise is outside kit |
| Node-only primitive fails before strip | Browser-safe Web APIs only; raw parser private | Build plus no-`Buffer` browser probe | Block release | Actual bundler/bootstrap still requires independent review |
| Base64url alias bypass | Exact 32-byte decode and canonical re-encode | Alias and generation tests | Reject locally | Producer randomness cannot be inferred from token text |
| Secret escapes through raw parser | No parser or secret-byte export; strip-first session only | Compile and runtime export-surface tests | Block incompatible API change | Calling callback can still copy secret bytes |
| Secret persistence | No storage, cookie, DB, or filesystem adapter exists | Source/path review | Remove integration and rotate/revoke | Calling application can add unsafe persistence |

## Mandatory review gate

An independent frontend security review must inspect the actual application
bootstrap order, deployed response headers, CSP, analytics/tag manager loading,
service workers, error reporting, browser history, clipboard/share UI, DOM, and
mobile webview behavior. Unit tests in this kit cannot close that gate.

No deployment claim may state that fragment secrecy is proven until that review
is completed against the deployed frontend.
