import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import { runSecurityCases } from "../../../../packages/channel-protocol/typescript/src/conformance-runner.js";

const root = resolve(process.cwd(), "../../..");

test("TypeScript rejects every signed-preimage mutation without authority effect", () => {
  const results = runSecurityCases(
    resolve(root, "tests/channels/security/replay/mutation-cases.json"),
    resolve(root, "contracts/channel/canonicalization"),
  );
  const expectations = JSON.parse(
    readFileSync(
      resolve(
        root,
        "contracts/channel/test-vectors/negative/fc-sec-002/signed-preimage-mutations-v1.json",
      ),
      "utf8",
    ),
  ) as { expectations: Array<Record<string, unknown>>; runner_reads_expectations: boolean };

  assert.equal(results.length, 23);
  assert.equal(expectations.runner_reads_expectations, false);
  for (const [index, result] of results.entries()) {
    assert.equal(result.decision, "reject");
    assert.equal(result.economic_effect_count, 0);
    assert.equal(result.authority_advancement_count, 0);
    assert.equal(result.lifecycle_transition_count, 0);
    assert.equal(result.verified_transition_count, 0);
    assert.equal(result.activation_requested_transition_count, 0);
    assert.equal(result.authorized_transition_count, 0);
    assert.equal(result.completed_transition_count, 0);
    const {
      implementation: _implementation,
      runtime_version: _runtimeVersion,
      runner_contract: _runnerContract,
      runner_version: _runnerVersion,
      schema_version: _schemaVersion,
      ...comparable
    } = result;
    assert.deepEqual(comparable, expectations.expectations[index]);
  }
});
