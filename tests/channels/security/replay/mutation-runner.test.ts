import assert from "node:assert/strict";
import { resolve } from "node:path";
import test from "node:test";

import { runSecurityCases } from "../../../../packages/channel-protocol/typescript/src/conformance-runner.js";

const root = resolve(process.cwd(), "../../..");

test("TypeScript rejects every signed-preimage mutation without authority effect", () => {
  const results = runSecurityCases(
    resolve(root, "tests/channels/security/replay/mutation-cases.json"),
    resolve(root, "contracts/channel/canonicalization"),
  );

  assert.equal(results.length, 23);
  for (const result of results) {
    assert.equal(result.decision, "reject");
    assert.equal(result.economic_effect_count, 0);
    assert.equal(result.authority_advancement_count, 0);
    assert.equal(result.lifecycle_transition_count, 0);
    assert.equal(result.verified_transition_count, 0);
    assert.equal(result.activation_requested_transition_count, 0);
    assert.equal(result.authorized_transition_count, 0);
    assert.equal(result.completed_transition_count, 0);
  }
});
