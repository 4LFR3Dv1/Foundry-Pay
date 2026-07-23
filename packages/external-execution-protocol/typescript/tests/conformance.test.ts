import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  DomainNormalizationError,
  canonicalize,
  economicPlanHash,
  executionCommitmentHash,
  normalizeEconomicPlan,
  preparedMessageHash,
  simulationAttestationHash,
} from "../src/canonicalization.js";

type JsonObject = Record<string, unknown>;

const vector = JSON.parse(
  readFileSync(
    new URL("../../../conformance/vectors/protocol-v1.json", import.meta.url),
    "utf8",
  ),
) as JsonObject;
const negativeVectors = JSON.parse(
  readFileSync(new URL("../../../conformance/vectors/negative-v1.json", import.meta.url), "utf8"),
) as { cases: Array<{ id: string; target: string; path: string[]; value: unknown }> };

function clone<T>(value: T): T {
  return structuredClone(value);
}

function setPath(target: JsonObject, path: string[], value: unknown): void {
  let cursor: JsonObject = target;
  path.slice(0, -1).forEach((segment) => {
    const next = cursor[segment];
    assert.equal(typeof next, "object");
    assert.notEqual(next, null);
    cursor = next as JsonObject;
  });
  const final = path.at(-1);
  assert.ok(final);
  cursor[final] = value;
}

test("positive vector produces normative bytes and hashes", () => {
  const plan = vector.economic_plan;
  const commitment = vector.execution_commitment;
  assert.equal(
    Buffer.from(canonicalize(normalizeEconomicPlan(plan))).toString("hex"),
    vector.economic_plan_canonical_hex,
  );
  assert.equal(economicPlanHash(plan), vector.economic_plan_hash);
  assert.equal(
    preparedMessageHash(Buffer.from(vector.prepared_message_hex as string, "hex")),
    vector.prepared_message_hash,
  );
  assert.equal(
    simulationAttestationHash(vector.simulation_attestation),
    vector.simulation_attestation_hash,
  );
  assert.equal(
    Buffer.from(canonicalize(commitment)).toString("hex"),
    vector.execution_commitment_canonical_hex,
  );
  assert.equal(executionCommitmentHash(commitment), vector.execution_commitment_hash);
});

test("all shared negative vectors fail", () => {
  for (const negative of negativeVectors.cases) {
    const target = clone(
      negative.target === "economic_plan"
        ? (vector.economic_plan as JsonObject)
        : (vector.execution_commitment as JsonObject),
    );
    setPath(target, negative.path, negative.value);
    assert.throws(
      () =>
        negative.target === "economic_plan"
          ? economicPlanHash(target)
          : executionCommitmentHash(target),
      DomainNormalizationError,
      negative.id,
    );
  }
});

test("object ordering is immaterial and array ordering remains material", () => {
  const plan = vector.economic_plan as JsonObject;
  const reordered = Object.fromEntries(Object.entries(plan).reverse());
  assert.equal(economicPlanHash(reordered), economicPlanHash(plan));

  const commitment = clone(vector.execution_commitment as JsonObject);
  const constraints = commitment.constraints as JsonObject;
  constraints.allowed_programs = [
    "11111111111111111111111111111111",
    "SysvarRent111111111111111111111111111111111",
  ];
  const original = executionCommitmentHash(commitment);
  constraints.allowed_programs = [...(constraints.allowed_programs as unknown[])].reverse();
  assert.notEqual(executionCommitmentHash(commitment), original);
});

test("single-field tampering changes the economic hash", () => {
  const plan = clone(vector.economic_plan as JsonObject);
  const original = economicPlanHash(plan);
  plan.amount_base_units = "1000001";
  assert.notEqual(economicPlanHash(plan), original);
});

test("unsupported JavaScript numeric values fail", () => {
  for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, -0, 1.5]) {
    assert.throws(() => canonicalize({ value }), DomainNormalizationError);
  }
  assert.throws(
    () => canonicalize({ value: Number.MAX_SAFE_INTEGER + 1 }),
    DomainNormalizationError,
  );
  assert.throws(() => canonicalize({ value: new Date() }), DomainNormalizationError);
});

test("Unicode is preserved and never normalized silently", () => {
  const composed = clone(vector.economic_plan as JsonObject);
  const decomposed = clone(vector.economic_plan as JsonObject);
  composed.reason = "\u00e9";
  decomposed.reason = "e\u0301";
  assert.notDeepEqual(canonicalize(composed), canonicalize(decomposed));
  assert.notEqual(economicPlanHash(composed), economicPlanHash(decomposed));
  assert.throws(() => canonicalize({ value: "\ud800" }), DomainNormalizationError);
});
