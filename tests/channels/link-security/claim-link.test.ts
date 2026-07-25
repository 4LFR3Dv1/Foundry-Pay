import assert from "node:assert/strict";
import test from "node:test";

import {
  ClaimLinkError,
  ClaimLinkSession,
  generateOpaqueToken,
  parseClaimLink,
  safeClaimUrl,
  validateLocator,
} from "../../../packages/channel-protocol/typescript/src/index.js";

const LOCATOR = Buffer.alloc(32, 0x4c).toString("base64url");
const SECRET = Buffer.alloc(32, 0x53).toString("base64url");
const CLAIM_URL = `https://foundry.pay/claim/${LOCATOR}#${SECRET}`;

test("parses an exact claim URL and derives a fragment-free replacement", () => {
  const parsed = parseClaimLink(CLAIM_URL);
  assert.equal(parsed.locator, LOCATOR);
  assert.equal(parsed.safeReplacementUrl, `https://foundry.pay/claim/${LOCATOR}`);
  assert.ok(parsed.secretBytes.byteLength >= 32);
  assert.ok(!parsed.safeReplacementUrl.includes(SECRET));
});

test("rejects unsafe origins, paths, query strings, locators, and secrets", () => {
  const invalid = [
    `http://foundry.pay/claim/${LOCATOR}#${SECRET}`,
    `https://evil.example/claim/${LOCATOR}#${SECRET}`,
    `https://foundry.pay/other/${LOCATOR}#${SECRET}`,
    `https://foundry.pay/claim/${LOCATOR}/extra#${SECRET}`,
    `https://foundry.pay/claim/${LOCATOR}?track=1#${SECRET}`,
    `https://foundry.pay/claim/short#${SECRET}`,
    `https://foundry.pay/claim/${LOCATOR}`,
    `https://foundry.pay/claim/${LOCATOR}#short`,
    `https://user:password@foundry.pay/claim/${LOCATOR}#${SECRET}`,
  ];
  for (const candidate of invalid) {
    assert.throws(() => parseClaimLink(candidate), ClaimLinkError);
  }
});

test("opens by stripping the fragment before exposing a consumable session", () => {
  const replacements: string[] = [];
  const session = ClaimLinkSession.open(CLAIM_URL, {
    replaceState: (_data, _unused, url) => replacements.push(String(url)),
  });

  assert.deepEqual(replacements, [`https://foundry.pay/claim/${LOCATOR}`]);
  assert.equal(session.consumed, false);
  let observed = "";
  session.consume((secret) => {
    observed = Buffer.from(secret).toString("base64url");
  });
  assert.equal(observed, SECRET);
  assert.equal(session.consumed, true);
  assert.throws(() => session.consume(() => undefined), /claim_secret_already_consumed/u);
});

test("zeroizes the ephemeral secret buffer after consume", () => {
  const session = ClaimLinkSession.open(CLAIM_URL, { replaceState: () => undefined });
  let retained: Uint8Array | undefined;
  session.consume((secret) => {
    retained = secret;
  });
  assert.ok(retained);
  assert.ok(retained.every((byte) => byte === 0));
});

test("fails closed when the fragment cannot be removed", () => {
  assert.throws(
    () =>
      ClaimLinkSession.open(CLAIM_URL, {
        replaceState: () => {
          throw new Error(`unsafe browser error: ${CLAIM_URL}`);
        },
      }),
    (error: unknown) =>
      error instanceof ClaimLinkError &&
      error.code === "fragment_removal_failed" &&
      !error.message.includes(SECRET),
  );
});

test("safe share/clipboard output contains locator but never fragment secret", () => {
  const output = safeClaimUrl(LOCATOR);
  assert.equal(output, `https://foundry.pay/claim/${LOCATOR}`);
  assert.ok(!output.includes("#"));
  assert.ok(!output.includes(SECRET));
});

test("opaque token generation requires 32 random bytes and yields 256-bit identifiers", () => {
  let counter = 0;
  const first = generateOpaqueToken((target) => {
    target.fill(counter++);
    return target;
  });
  const second = generateOpaqueToken((target) => {
    target.fill(counter++);
    return target;
  });
  assert.equal(Buffer.from(first, "base64url").byteLength, 32);
  assert.equal(Buffer.from(second, "base64url").byteLength, 32);
  assert.notEqual(first, second);
  assert.equal(validateLocator(first), first);
});
