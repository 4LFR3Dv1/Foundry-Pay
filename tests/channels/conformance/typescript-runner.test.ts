import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import test from "node:test";

import { runRegistry } from "../../../packages/channel-protocol/typescript/src/conformance-runner.js";

const ROOT = resolve(import.meta.dirname, "../../../../../../..");
const REGISTRY = join(ROOT, "contracts/channel/canonicalization");

function load(path: string): Record<string, unknown> {
  return JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>;
}

test("TypeScript runner independently recomputes all frozen vectors", () => {
  const results = runRegistry(REGISTRY);
  assert.equal(results.length, 28);
  assert.deepEqual(
    results.map((item) => item.vector_id),
    results.map((item) => item.vector_id).sort(),
  );
  const byId = new Map(results.map((item) => [item.vector_id, item]));
  const manifest = load(join(REGISTRY, "manifest.v1.json"));
  for (const filename of manifest["positive_vectors"] as string[]) {
    const vector = load(join(REGISTRY, "positive", filename));
    const result = byId.get(vector["vector_id"] as string);
    assert.ok(result);
    assert.equal(
      result.canonical_utf8_hex,
      (vector["canonical_utf8_hex"] as string | null) ?? vector["source_bytes_hex"],
    );
    assert.equal(result.byte_length, vector["byte_length"]);
    assert.equal(result.sha256, vector["expected_sha256"]);
  }
  for (const filename of manifest["negative_vectors"] as string[]) {
    const vector = load(join(REGISTRY, "negative", filename));
    const result = byId.get(vector["vector_id"] as string);
    assert.ok(result);
    assert.equal(result.stage, vector["rejection_stage"]);
    assert.equal(result.code, vector["expected_rejection_code"]);
  }
});
