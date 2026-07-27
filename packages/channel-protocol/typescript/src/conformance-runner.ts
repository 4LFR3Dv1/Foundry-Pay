import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

import canonicalize from "canonicalize";

type JsonPrimitive = null | boolean | number | string;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
type JsonObject = { [key: string]: JsonValue };

type Vector = {
  vector_id: string;
  profile_id?: string;
  source_bytes_hex?: string;
  source_json?: string;
  excluded_fields?: string[];
  input?: JsonValue;
};

type RunnerResult = {
  schema_version: 1;
  runner_contract: "foundry.channels.conformance-runner-result/1";
  implementation: "typescript";
  runtime_version: string;
  runner_version: "1.0.0";
  vector_id: string;
  vector_kind: "positive" | "negative";
  decision: "accept" | "reject";
  stage: string;
  code: string;
  canonical_utf8_hex?: string;
  canonical_utf8_base64?: string;
  byte_length?: number;
  sha256?: string;
};

const RUNNER_CONTRACT = "foundry.channels.conformance-runner-result/1" as const;
const RUNNER_VERSION = "1.0.0" as const;
const JSON_SAFE_UNSIGNED_MAX = 9_007_199_254_740_991n;
const U64_MAX = 18_446_744_073_709_551_615n;
const HASH = /^sha256:[0-9a-f]{64}$/;
const AMOUNT = /^(0|[1-9][0-9]*)$/;
const TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

export class ConformanceRejection extends Error {
  readonly code: string;
  readonly stage: string;

  constructor(code: string, stage: string, detail: string) {
    super(`${stage}:${code}: ${detail}`);
    this.name = "ConformanceRejection";
    this.code = code;
    this.stage = stage;
  }
}

function reject(code: string, stage: string, detail: string): never {
  throw new ConformanceRejection(code, stage, detail);
}

class StrictJsonParser {
  private index = 0;

  constructor(private readonly source: string) {}

  parse(): JsonValue {
    this.skipWhitespace();
    const value = this.parseValue();
    this.skipWhitespace();
    if (this.index !== this.source.length) {
      reject("malformed_json", "parse", "trailing input");
    }
    validateJsonValue(value);
    return value;
  }

  private parseValue(): JsonValue {
    this.skipWhitespace();
    const character = this.source[this.index];
    if (character === "{") return this.parseObject();
    if (character === "[") return this.parseArray();
    if (character === '"') return this.parseString();
    if (character === "-" || (character !== undefined && /[0-9]/.test(character))) {
      return this.parseNumber();
    }
    if (this.source.startsWith("true", this.index)) {
      this.index += 4;
      return true;
    }
    if (this.source.startsWith("false", this.index)) {
      this.index += 5;
      return false;
    }
    if (this.source.startsWith("null", this.index)) {
      this.index += 4;
      return null;
    }
    if (
      this.source.startsWith("NaN", this.index) ||
      this.source.startsWith("Infinity", this.index)
    ) {
      reject("non_finite_number", "parse", "non-finite JSON number");
    }
    reject("malformed_json", "parse", `unexpected token at offset ${this.index}`);
  }

  private parseObject(): JsonObject {
    this.index += 1;
    const result: JsonObject = {};
    const keys = new Set<string>();
    this.skipWhitespace();
    if (this.source[this.index] === "}") {
      this.index += 1;
      return result;
    }
    while (true) {
      this.skipWhitespace();
      if (this.source[this.index] !== '"') {
        reject("malformed_json", "parse", "object key must be a string");
      }
      const key = this.parseString();
      if (keys.has(key)) reject("duplicate_key", "parse", `duplicate key ${key}`);
      keys.add(key);
      this.skipWhitespace();
      if (this.source[this.index] !== ":") {
        reject("malformed_json", "parse", "missing object colon");
      }
      this.index += 1;
      result[key] = this.parseValue();
      this.skipWhitespace();
      const separator = this.source[this.index];
      if (separator === "}") {
        this.index += 1;
        return result;
      }
      if (separator !== ",") reject("malformed_json", "parse", "invalid object separator");
      this.index += 1;
    }
  }

  private parseArray(): JsonValue[] {
    this.index += 1;
    const result: JsonValue[] = [];
    this.skipWhitespace();
    if (this.source[this.index] === "]") {
      this.index += 1;
      return result;
    }
    while (true) {
      result.push(this.parseValue());
      this.skipWhitespace();
      const separator = this.source[this.index];
      if (separator === "]") {
        this.index += 1;
        return result;
      }
      if (separator !== ",") reject("malformed_json", "parse", "invalid array separator");
      this.index += 1;
    }
  }

  private parseString(): string {
    const start = this.index;
    this.index += 1;
    let escaped = false;
    while (this.index < this.source.length) {
      const character = this.source[this.index]!;
      if (escaped) {
        escaped = false;
        this.index += 1;
        continue;
      }
      if (character === "\\") {
        escaped = true;
        this.index += 1;
        continue;
      }
      if (character === '"') {
        this.index += 1;
        try {
          return JSON.parse(this.source.slice(start, this.index)) as string;
        } catch {
          reject("malformed_json", "parse", "invalid JSON string");
        }
      }
      if (character.charCodeAt(0) < 0x20) {
        reject("malformed_json", "parse", "unescaped control character");
      }
      this.index += 1;
    }
    reject("malformed_json", "parse", "unterminated string");
  }

  private parseNumber(): number {
    const remaining = this.source.slice(this.index);
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(remaining);
    if (match === null) reject("malformed_json", "parse", "invalid JSON number");
    const token = match[0];
    this.index += token.length;
    if (Object.is(Number(token), -0)) reject("negative_zero", "parse", "negative zero");
    if (/[.eE]/.test(token)) reject("float_forbidden", "parse", "floating point number");
    const integer = BigInt(token);
    if (integer < 0n || integer > JSON_SAFE_UNSIGNED_MAX) {
      reject("unsafe_integer", "parse", "integer is outside the safe unsigned range");
    }
    return Number(integer);
  }

  private skipWhitespace(): void {
    while (this.index < this.source.length && /\s/.test(this.source[this.index]!)) {
      this.index += 1;
    }
  }
}

function validateJsonValue(value: JsonValue): void {
  if (value === null) reject("null_forbidden", "projection", "null values must be omitted");
  if (typeof value === "string") {
    for (let index = 0; index < value.length; index += 1) {
      const code = value.charCodeAt(index);
      if (code >= 0xd800 && code <= 0xdbff) {
        const next = value.charCodeAt(index + 1);
        if (!(next >= 0xdc00 && next <= 0xdfff)) {
          reject("lone_surrogate", "canonicalization", "unpaired high surrogate");
        }
        index += 1;
      } else if (code >= 0xdc00 && code <= 0xdfff) {
        reject("lone_surrogate", "canonicalization", "unpaired low surrogate");
      }
    }
  } else if (Array.isArray(value)) {
    for (const item of value) validateJsonValue(item);
  } else if (typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      validateJsonValue(key);
      validateJsonValue(item);
    }
  }
}

function strictParse(value: string): JsonValue {
  return new StrictJsonParser(value).parse();
}

function canonicalBytes(value: JsonValue): Buffer {
  validateJsonValue(value);
  const serialized = canonicalize(value);
  if (serialized === undefined) reject("jcs_rejected", "canonicalization", "unsupported value");
  return Buffer.from(serialized, "utf8");
}

function sha256(value: Uint8Array): string {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

function loadObject(path: string): JsonObject {
  const value = JSON.parse(readFileSync(path, "utf8")) as JsonValue;
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new Error(`${path}: expected object`);
  }
  return value;
}

function positiveBytes(vector: Vector): Buffer {
  if (
    vector.profile_id === "raw-bytes-commitment-v1" ||
    vector.profile_id === "evidence-artifact-v1"
  ) {
    if (typeof vector.source_bytes_hex !== "string") throw new Error("source_bytes_hex missing");
    return Buffer.from(vector.source_bytes_hex, "hex");
  }
  if (typeof vector.source_json !== "string") throw new Error("source_json missing");
  const source = strictParse(vector.source_json);
  if (source === null || Array.isArray(source) || typeof source !== "object") {
    throw new Error("source_json must contain an object");
  }
  let projection: JsonValue;
  if (vector.profile_id === "signed-payload-v1") {
    projection = source["payload"]!;
  } else if (
    vector.profile_id === "self-hashed-record-v1" ||
    vector.profile_id === "journal-chain-v1"
  ) {
    if (!Array.isArray(vector.excluded_fields)) throw new Error("excluded_fields missing");
    const excluded = new Set(vector.excluded_fields);
    for (const field of excluded) {
      if (!(field in source)) throw new Error(`excluded field missing: ${field}`);
    }
    projection = Object.fromEntries(Object.entries(source).filter(([key]) => !excluded.has(key)));
  } else if (vector.profile_id === "canonical-record-v1") {
    projection = source;
  } else {
    throw new Error(`unsupported profile ${vector.profile_id}`);
  }
  return canonicalBytes(projection);
}

function validateMinimalClosedObject(value: JsonValue | undefined): void {
  if (value === null || value === undefined || Array.isArray(value) || typeof value !== "object") {
    reject("invalid_record", "schema", "expected object");
  }
  const allowed = new Set(["domain", "mint"]);
  const unknown = Object.keys(value).filter((key) => !allowed.has(key)).sort();
  if (unknown.length > 0) reject("unknown_field", "schema", `unknown field ${unknown[0]}`);
  for (const field of ["domain", "mint"]) {
    if (!(field in value)) reject("missing_field", "schema", `missing field ${field}`);
  }
}

function validateUnsignedInteger(value: JsonValue | undefined): void {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    reject("invalid_integer", "schema", "expected unsigned safe integer");
  }
}

function validateAmount(value: JsonValue | undefined): void {
  if (typeof value !== "string" || !AMOUNT.test(value)) {
    reject("invalid_amount", "schema", "expected canonical decimal amount");
  }
  if (BigInt(value) > U64_MAX) reject("amount_out_of_range", "schema", "amount exceeds u64");
}

function validateTimestamp(value: JsonValue | undefined): void {
  if (typeof value !== "string" || !TIMESTAMP.test(value)) {
    reject("invalid_timestamp", "schema", "timestamp format");
  }
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().replace(".000Z", "Z") !== value) {
    reject("invalid_timestamp", "schema", "impossible timestamp");
  }
}

function validateCanonicalSet(value: JsonValue | undefined): void {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    reject("invalid_canonical_set", "projection", "expected string array");
  }
  const strings = value as string[];
  if (new Set(strings).size !== strings.length) {
    reject("canonical_set_duplicate", "projection", "duplicate element");
  }
  const sorted = [...strings].sort();
  if (strings.some((item, index) => item !== sorted[index])) {
    reject("canonical_set_order", "projection", "non-canonical order");
  }
}

function verifyDeclaredHash(value: JsonValue | undefined, expected: string): void {
  if (typeof value !== "string" || !HASH.test(value)) {
    reject("invalid_hash", "hash_verification", "non-canonical hash");
  }
  if (value !== expected) reject("hash_mismatch", "hash_verification", "hash differs");
}

function exerciseNegative(vector: Vector, registeredDomains: Set<string>): void {
  const value = vector.input;
  switch (vector.vector_id) {
    case "duplicate-keys":
    case "float":
    case "nan":
    case "infinity":
    case "negative-zero":
    case "null":
    case "unsafe-integer":
      if (typeof value !== "string") throw new Error("string input required");
      strictParse(value);
      return;
    case "unknown-field":
    case "missing-field":
      validateMinimalClosedObject(value);
      return;
    case "bool-as-integer":
      validateUnsignedInteger(value);
      return;
    case "u64-overflow":
    case "amount-leading-zero":
      validateAmount(value);
      return;
    case "malformed-timestamp":
      validateTimestamp(value);
      return;
    case "lone-surrogate": {
      if (value !== "\\ud800") throw new Error("frozen lone-surrogate escape changed");
      canonicalBytes({ value: JSON.parse(`"${value}"`) as string });
      return;
    }
    case "unregistered-domain":
      if (typeof value !== "string" || !registeredDomains.has(value)) {
        reject("domain_unregistered", "domain_verification", "domain is not registered");
      }
      return;
    case "uppercase-hash":
    case "short-hash":
      verifyDeclaredHash(value, `sha256:${"a".repeat(64)}`);
      return;
    case "own-hash-in-preimage": {
      if (value === null || Array.isArray(value) || typeof value !== "object") {
        throw new Error("record input required");
      }
      const declared = value["receipt_hash"];
      const projection = Object.fromEntries(
        Object.entries(value).filter(([key]) => key !== "receipt_hash"),
      );
      verifyDeclaredHash(declared, sha256(canonicalBytes(projection)));
      return;
    }
    case "canonical-set-order":
    case "canonical-set-duplicate":
      validateCanonicalSet(value);
      return;
    default:
      throw new Error(`no independent negative executor for ${vector.vector_id}`);
  }
}

function baseResult(vectorId: string, vectorKind: "positive" | "negative"): RunnerResult {
  return {
    schema_version: 1,
    runner_contract: RUNNER_CONTRACT,
    implementation: "typescript",
    runtime_version: process.versions.node,
    runner_version: RUNNER_VERSION,
    vector_id: vectorId,
    vector_kind: vectorKind,
    decision: vectorKind === "positive" ? "accept" : "reject",
    stage: vectorKind === "positive" ? "complete" : "",
    code: vectorKind === "positive" ? "ok" : "",
  };
}

export function runRegistry(registryRoot: string): RunnerResult[] {
  const manifest = loadObject(join(registryRoot, "manifest.v1.json"));
  const domainRegistry = loadObject(join(registryRoot, "domains.v1.json"));
  const registeredDomains = new Set(
    (domainRegistry["domains"] as JsonObject[]).map((entry) => entry["domain"] as string),
  );
  const entries: Array<{ kind: "positive" | "negative"; vector: Vector }> = [];
  for (const [kind, key] of [
    ["positive", "positive_vectors"],
    ["negative", "negative_vectors"],
  ] as const) {
    const names = manifest[key];
    if (!Array.isArray(names) || names.some((name) => typeof name !== "string")) {
      throw new Error(`manifest ${key} is invalid`);
    }
    for (const name of names as string[]) {
      entries.push({
        kind,
        vector: loadObject(join(registryRoot, kind, name)) as unknown as Vector,
      });
    }
  }
  entries.sort((left, right) => left.vector.vector_id.localeCompare(right.vector.vector_id));
  if (new Set(entries.map((entry) => entry.vector.vector_id)).size !== entries.length) {
    throw new Error("duplicate vector_id");
  }
  return entries.map(({ kind, vector }) => {
    if (kind === "positive") {
      const payload = positiveBytes(vector);
      return {
        ...baseResult(vector.vector_id, "positive"),
        canonical_utf8_hex: payload.toString("hex"),
        canonical_utf8_base64: payload.toString("base64"),
        byte_length: payload.length,
        sha256: sha256(payload),
      };
    }
    try {
      exerciseNegative(vector, registeredDomains);
    } catch (error) {
      if (error instanceof ConformanceRejection) {
        return {
          ...baseResult(vector.vector_id, "negative"),
          stage: error.stage,
          code: error.code,
        };
      }
      throw error;
    }
    throw new Error(`${vector.vector_id}: negative vector was accepted`);
  });
}

function parseRegistryRoot(arguments_: string[]): string {
  const index = arguments_.indexOf("--registry-root");
  const value = index < 0 ? undefined : arguments_[index + 1];
  if (value === undefined) {
    throw new Error("--registry-root is required");
  }
  return resolve(value);
}

function main(): number {
  try {
    for (const result of runRegistry(parseRegistryRoot(process.argv.slice(2)))) {
      process.stdout.write(`${JSON.stringify(result)}\n`);
    }
    return 0;
  } catch (error) {
    process.stderr.write(`typescript conformance runner failed: ${String(error)}\n`);
    return 2;
  }
}

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  process.exitCode = main();
}
