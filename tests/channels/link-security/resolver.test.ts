import assert from "node:assert/strict";
import test from "node:test";

import {
  buildResolverRequest,
  ClaimLinkError,
  resolveClaim,
} from "../../../packages/channel-protocol/typescript/src/index.js";

const LOCATOR = Buffer.alloc(32, 0x4c).toString("base64url");
const SECRET = Buffer.alloc(32, 0x53).toString("base64url");

test("resolver request transports only the locator path under browser fragment semantics", () => {
  const browserUrl = new URL(`https://foundry.pay/claim/${LOCATOR}#${SECRET}`);
  // This is the same URL material available to HTTP: browsers never send hash.
  const httpVisibleUrl = `${browserUrl.origin}${browserUrl.pathname}${browserUrl.search}`;
  const request = buildResolverRequest(LOCATOR);

  assert.equal(request.url, httpVisibleUrl);
  assert.equal(new URL(request.url).hash, "");
  assert.equal(request.referrerPolicy, "no-referrer");
  assert.equal(request.headers["cache-control"], "no-store");
  assert.ok(!JSON.stringify(request).includes(SECRET));
});

test("local fake transport observes no claim secret or fragment", async () => {
  let wire = "";
  const result = await resolveClaim(LOCATOR, async (request) => {
    wire = JSON.stringify(request);
    return {
      ok: true,
      json: async () => ({ status: "available" }),
    };
  });
  assert.deepEqual(result, { status: "available" });
  assert.ok(!wire.includes(SECRET));
  assert.ok(!wire.includes("#"));
  assert.equal(new URL(JSON.parse(wire).url as string).pathname, `/claim/${LOCATOR}`);
});

test("missing, blocked, expired, malformed response, and transport failure are uniform", async () => {
  const transports = [
    async () => ({ ok: false, json: async () => ({ reason: "missing" }) }),
    async () => ({ ok: false, json: async () => ({ reason: "blocked" }) }),
    async () => ({ ok: false, json: async () => ({ reason: "expired" }) }),
    async () => ({ ok: true, json: async () => Promise.reject(new Error("malformed")) }),
    async () => Promise.reject(new Error("offline")),
  ];
  for (const transport of transports) {
    await assert.rejects(
      resolveClaim(LOCATOR, transport),
      (error: unknown) =>
        error instanceof ClaimLinkError && error.code === "claim_unavailable",
    );
  }
});
