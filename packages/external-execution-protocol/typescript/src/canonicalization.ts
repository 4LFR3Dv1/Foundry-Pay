import { createHash } from "node:crypto";

export const PROFILE = "foundry-pay-domain-v1";
export const PROTOCOL_VERSION = "1.0.0";
export const NETWORK = "solana:devnet";
export const CAPABILITY = "solana.spl_transfer.v1";
export const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

const IDENTIFIER = /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/u;
const AMOUNT = /^(0|[1-9][0-9]*)$/u;
const TIMESTAMP =
  /^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$/u;
const SHA256 = /^sha256:[0-9a-f]{64}$/u;
const BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const BASE58_INDEX = new Map([...BASE58_ALPHABET].map((character, index) => [character, index]));

const PLAN_REQUIRED = new Set([
  "protocol_version",
  "normalization_profile",
  "obligation_id",
  "network",
  "capability",
  "asset",
  "amount_base_units",
  "source",
  "destination",
  "expires_at",
]);
const PLAN_OPTIONAL = new Set(["reason"]);
const COMMITMENT_REQUIRED = new Set([
  "protocol_version",
  "normalization_profile",
  "execution_request_id",
  "obligation_id",
  "executor_id",
  "executor_version",
  "economic_plan_hash",
  "prepared_message_hash",
  "simulation_attestation_hash",
  "signer",
  "constraints",
  "expires_at",
]);

type JsonObject = Record<string, unknown>;

export class DomainNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DomainNormalizationError";
  }
}

function isObject(value: unknown): value is JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype: object | null = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function rejectLoneSurrogates(value: string, path: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
        throw new DomainNormalizationError(`${path}: lone Unicode surrogate is forbidden`);
      }
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new DomainNormalizationError(`${path}: lone Unicode surrogate is forbidden`);
    }
  }
}

function assertSupportedJson(value: unknown, path = "$"): void {
  if (value === null) {
    throw new DomainNormalizationError(`${path}: null is forbidden`);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value) || !Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new DomainNormalizationError(`${path}: unsupported numeric value`);
    }
    return;
  }
  if (typeof value === "string") {
    rejectLoneSurrogates(value, path);
    return;
  }
  if (typeof value === "boolean") {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((child, index) => assertSupportedJson(child, `${path}[${index}]`));
    return;
  }
  if (isObject(value)) {
    for (const [key, child] of Object.entries(value)) {
      rejectLoneSurrogates(key, `${path}.<key>`);
      assertSupportedJson(child, `${path}.${key}`);
    }
    return;
  }
  throw new DomainNormalizationError(`${path}: unsupported JSON type`);
}

function requireClosedKeys(
  value: JsonObject,
  required: ReadonlySet<string>,
  optional: ReadonlySet<string>,
  path: string,
): void {
  const keys = new Set(Object.keys(value));
  const missing = [...required].filter((key) => !keys.has(key));
  const unknown = [...keys].filter((key) => !required.has(key) && !optional.has(key));
  if (missing.length > 0) {
    throw new DomainNormalizationError(`${path}: missing keys: ${missing.sort().join(", ")}`);
  }
  if (unknown.length > 0) {
    throw new DomainNormalizationError(`${path}: unknown keys: ${unknown.sort().join(", ")}`);
  }
}

function requireIdentifier(value: unknown, path: string): string {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) {
    throw new DomainNormalizationError(`${path}: invalid identifier`);
  }
  return value;
}

function requireTimestamp(value: unknown, path: string): string {
  if (typeof value !== "string" || !TIMESTAMP.test(value)) {
    throw new DomainNormalizationError(`${path}: expected UTC RFC 3339 with second precision`);
  }
  return value;
}

function decodeBase58(value: string): Uint8Array {
  let number = 0n;
  for (const character of value) {
    const digit = BASE58_INDEX.get(character);
    if (digit === undefined) {
      throw new DomainNormalizationError("invalid base58 character");
    }
    number = number * 58n + BigInt(digit);
  }
  const decoded: number[] = [];
  while (number > 0n) {
    decoded.push(Number(number % 256n));
    number /= 256n;
  }
  decoded.reverse();
  const leadingZeroes = value.length - value.replace(/^1+/u, "").length;
  return Uint8Array.from([...new Array<number>(leadingZeroes).fill(0), ...decoded]);
}

function requireSolanaPubkey(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length < 32 || value.length > 44) {
    throw new DomainNormalizationError(`${path}: invalid Solana public key length`);
  }
  if (decodeBase58(value).length !== 32) {
    throw new DomainNormalizationError(`${path}: Solana public key must decode to 32 bytes`);
  }
  return value;
}

function requireHash(value: unknown, path: string): string {
  if (typeof value !== "string" || !SHA256.test(value)) {
    throw new DomainNormalizationError(`${path}: invalid sha256 digest`);
  }
  return value;
}

function serializeCanonical(value: unknown): string {
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(serializeCanonical).join(",")}]`;
  }
  if (isObject(value)) {
    const entries = Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${serializeCanonical(value[key])}`);
    return `{${entries.join(",")}}`;
  }
  throw new DomainNormalizationError("unsupported canonical JSON value");
}

export function normalizeEconomicPlan(plan: unknown): JsonObject {
  if (!isObject(plan)) {
    throw new DomainNormalizationError("$: economic plan must be an object");
  }
  assertSupportedJson(plan);
  requireClosedKeys(plan, PLAN_REQUIRED, PLAN_OPTIONAL, "$");
  if (plan.protocol_version !== PROTOCOL_VERSION) {
    throw new DomainNormalizationError("$.protocol_version: unsupported version");
  }
  if (plan.normalization_profile !== PROFILE) {
    throw new DomainNormalizationError("$.normalization_profile: unsupported profile");
  }
  requireIdentifier(plan.obligation_id, "$.obligation_id");
  if (plan.network !== NETWORK) {
    throw new DomainNormalizationError("$.network: unsupported network");
  }
  if (plan.capability !== CAPABILITY) {
    throw new DomainNormalizationError("$.capability: unsupported capability");
  }
  if (typeof plan.amount_base_units !== "string" || !AMOUNT.test(plan.amount_base_units)) {
    throw new DomainNormalizationError("$.amount_base_units: non-canonical amount");
  }
  if (BigInt(plan.amount_base_units) <= 0n) {
    throw new DomainNormalizationError("$.amount_base_units: must be greater than zero");
  }
  requireSolanaPubkey(plan.source, "$.source");
  requireSolanaPubkey(plan.destination, "$.destination");
  requireTimestamp(plan.expires_at, "$.expires_at");

  if (!isObject(plan.asset)) {
    throw new DomainNormalizationError("$.asset: must be an object");
  }
  requireClosedKeys(plan.asset, new Set(["kind", "mint", "decimals"]), new Set(), "$.asset");
  if (plan.asset.kind !== "spl-token") {
    throw new DomainNormalizationError("$.asset.kind: unsupported asset kind");
  }
  requireSolanaPubkey(plan.asset.mint, "$.asset.mint");
  if (
    typeof plan.asset.decimals !== "number" ||
    !Number.isSafeInteger(plan.asset.decimals) ||
    plan.asset.decimals < 0 ||
    plan.asset.decimals > 18
  ) {
    throw new DomainNormalizationError("$.asset.decimals: expected integer from 0 to 18");
  }
  if (
    "reason" in plan &&
    (typeof plan.reason !== "string" || plan.reason.length < 1 || plan.reason.length > 256)
  ) {
    throw new DomainNormalizationError("$.reason: expected 1 to 256 characters");
  }
  return { ...plan, asset: { ...plan.asset } };
}

export function canonicalize(value: unknown): Uint8Array {
  assertSupportedJson(value);
  return new TextEncoder().encode(serializeCanonical(value));
}

export function sha256Digest(payload: Uint8Array): string {
  return `sha256:${createHash("sha256").update(payload).digest("hex")}`;
}

export function economicPlanHash(plan: unknown): string {
  return sha256Digest(canonicalize(normalizeEconomicPlan(plan)));
}

export function preparedMessageHash(serializedMessage: Uint8Array): string {
  if (!(serializedMessage instanceof Uint8Array) || serializedMessage.length === 0) {
    throw new DomainNormalizationError("serialized message must be non-empty bytes");
  }
  return sha256Digest(serializedMessage);
}

export function simulationAttestationHash(attestation: unknown): string {
  if (!isObject(attestation)) {
    throw new DomainNormalizationError("simulation attestation must be an object");
  }
  return sha256Digest(canonicalize(attestation));
}

export function executionCommitmentHash(commitment: unknown): string {
  if (!isObject(commitment)) {
    throw new DomainNormalizationError("execution commitment must be an object");
  }
  assertSupportedJson(commitment);
  requireClosedKeys(commitment, COMMITMENT_REQUIRED, new Set(), "$");
  if (commitment.protocol_version !== PROTOCOL_VERSION) {
    throw new DomainNormalizationError("$.protocol_version: unsupported version");
  }
  if (commitment.normalization_profile !== PROFILE) {
    throw new DomainNormalizationError("$.normalization_profile: unsupported profile");
  }
  requireIdentifier(commitment.execution_request_id, "$.execution_request_id");
  requireIdentifier(commitment.obligation_id, "$.obligation_id");
  requireIdentifier(commitment.executor_id, "$.executor_id");
  if (typeof commitment.executor_version !== "string" || commitment.executor_version.length === 0) {
    throw new DomainNormalizationError("$.executor_version: required");
  }
  requireHash(commitment.economic_plan_hash, "$.economic_plan_hash");
  requireHash(commitment.prepared_message_hash, "$.prepared_message_hash");
  requireHash(commitment.simulation_attestation_hash, "$.simulation_attestation_hash");
  requireSolanaPubkey(commitment.signer, "$.signer");
  if (!isObject(commitment.constraints)) {
    throw new DomainNormalizationError("$.constraints: must be an object");
  }
  requireTimestamp(commitment.expires_at, "$.expires_at");
  return sha256Digest(canonicalize(commitment));
}
