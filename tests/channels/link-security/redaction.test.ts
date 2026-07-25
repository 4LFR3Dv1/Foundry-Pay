import assert from "node:assert/strict";
import test from "node:test";

import {
  REDACTED,
  redactString,
  redactUnknown,
  safeEvidencePayload,
  safeTelemetryPayload,
} from "../../../packages/channel-protocol/typescript/src/index.js";

const LOCATOR = Buffer.alloc(32, 0x4c).toString("base64url");
const SECRET = Buffer.alloc(32, 0x53).toString("base64url");
const URL = `https://foundry.pay/claim/${LOCATOR}#${SECRET}`;

function assertSecretAbsent(value: unknown): void {
  const serialized = JSON.stringify(value);
  assert.ok(!serialized.includes(SECRET));
  assert.ok(!serialized.includes(encodeURIComponent(SECRET)));
}

test("redacts full claim URLs and encoded fragment forms", () => {
  const encoded = encodeURIComponent(URL);
  const output = redactString(`raw=${URL} encoded=${encoded}`, [SECRET]);
  assertSecretAbsent(output);
  assert.match(output, new RegExp(REDACTED.replaceAll("[", "\\[").replaceAll("]", "\\]")));
});

test("redacts nested structures, keys, arrays, cycles, and errors", () => {
  const nested: Record<string, unknown> = {
    url: URL,
    analytics: [{ fragment: SECRET }, new Error(`failed for ${URL}`)],
    [`secret-${SECRET}`]: `encoded=${encodeURIComponent(SECRET)}`,
  };
  nested.self = nested;
  const output = redactUnknown(nested, [SECRET]);
  assertSecretAbsent(output);
  assert.equal((output as Record<string, unknown>).self, "[Circular]");
});

test("telemetry, logs, crash reports, and evidence use the same redaction boundary", () => {
  const unsafe = {
    log: URL,
    analytics: { page_location: URL },
    crash: new Error(SECRET),
    evidence: { copied_url: URL },
  };
  assertSecretAbsent(safeTelemetryPayload(unsafe, [SECRET]));
  assertSecretAbsent(safeEvidencePayload(unsafe, [SECRET]));
});
