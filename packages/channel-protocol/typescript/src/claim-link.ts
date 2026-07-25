const BASE64URL = /^[A-Za-z0-9_-]{43}$/u;
const CLAIM_PATH = /^\/claim\/([A-Za-z0-9_-]+)$/u;

export const DEFAULT_CLAIM_ORIGIN = "https://foundry.pay";
export const OPAQUE_TOKEN_BYTES = 32;

export class ClaimLinkError extends Error {
  readonly code: string;

  constructor(code: string) {
    super(code);
    this.name = "ClaimLinkError";
    this.code = code;
  }
}

interface ParsedClaimLink {
  readonly locator: string;
  readonly safeReplacementUrl: string;
  readonly secretBytes: Uint8Array;
}

function assertOpaqueValue(value: string, code: string): void {
  if (!BASE64URL.test(value)) {
    throw new ClaimLinkError(code);
  }
}

function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  let decoded: string;
  try {
    decoded = atob(normalized + padding);
  } catch {
    throw new ClaimLinkError("invalid_base64url");
  }
  return Uint8Array.from(decoded, (character) => character.charCodeAt(0));
}

function encodeBase64Url(value: Uint8Array): string {
  let binary = "";
  for (const byte of value) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

export type SecureRandom = (target: Uint8Array) => Uint8Array;

export function generateOpaqueToken(random: SecureRandom = crypto.getRandomValues.bind(crypto)): string {
  const bytes = new Uint8Array(OPAQUE_TOKEN_BYTES);
  const filled = random(bytes);
  if (filled !== bytes || bytes.byteLength !== OPAQUE_TOKEN_BYTES) {
    throw new ClaimLinkError("secure_random_failed");
  }
  return encodeBase64Url(bytes);
}

export function validateLocator(locator: string): string {
  assertOpaqueValue(locator, "invalid_claim_locator");
  const decoded = decodeBase64Url(locator);
  if (
    decoded.byteLength !== OPAQUE_TOKEN_BYTES ||
    encodeBase64Url(decoded) !== locator
  ) {
    throw new ClaimLinkError("invalid_claim_locator");
  }
  return locator;
}

function parseClaimLink(
  rawUrl: string,
  expectedOrigin = DEFAULT_CLAIM_ORIGIN,
): ParsedClaimLink {
  let url: URL;
  let origin: URL;
  try {
    url = new URL(rawUrl);
    origin = new URL(expectedOrigin);
  } catch {
    throw new ClaimLinkError("invalid_claim_url");
  }

  if (
    origin.protocol !== "https:" ||
    origin.pathname !== "/" ||
    origin.search !== "" ||
    origin.hash !== "" ||
    origin.username !== "" ||
    origin.password !== ""
  ) {
    throw new ClaimLinkError("invalid_expected_origin");
  }
  if (
    url.protocol !== "https:" ||
    url.origin !== origin.origin ||
    url.username !== "" ||
    url.password !== "" ||
    url.search !== ""
  ) {
    throw new ClaimLinkError("invalid_claim_origin");
  }

  const match = CLAIM_PATH.exec(url.pathname);
  if (match === null) {
    throw new ClaimLinkError("invalid_claim_path");
  }
  const locator = validateLocator(match[1] ?? "");
  const encodedSecret = url.hash.startsWith("#") ? url.hash.slice(1) : "";
  let secret: string;
  try {
    secret = decodeURIComponent(encodedSecret);
  } catch {
    throw new ClaimLinkError("invalid_claim_secret");
  }
  assertOpaqueValue(secret, "invalid_claim_secret");
  const secretBytes = decodeBase64Url(secret);
  if (
    secretBytes.byteLength !== OPAQUE_TOKEN_BYTES ||
    encodeBase64Url(secretBytes) !== secret
  ) {
    throw new ClaimLinkError("invalid_claim_secret");
  }

  return {
    locator,
    safeReplacementUrl: `${origin.origin}/claim/${locator}`,
    secretBytes,
  };
}

export interface HistoryReplacement {
  replaceState(data: unknown, unused: string, url?: string | URL | null): void;
}

export class ClaimLinkSession {
  readonly locator: string;
  readonly safeReplacementUrl: string;
  #secretBytes: Uint8Array | undefined;
  #consumed = false;

  private constructor(parsed: ParsedClaimLink) {
    this.locator = parsed.locator;
    this.safeReplacementUrl = parsed.safeReplacementUrl;
    this.#secretBytes = parsed.secretBytes;
  }

  static open(
    rawUrl: string,
    history: HistoryReplacement,
    expectedOrigin = DEFAULT_CLAIM_ORIGIN,
  ): ClaimLinkSession {
    const parsed = parseClaimLink(rawUrl, expectedOrigin);
    try {
      history.replaceState(null, "", parsed.safeReplacementUrl);
    } catch {
      parsed.secretBytes.fill(0);
      throw new ClaimLinkError("fragment_removal_failed");
    }
    return new ClaimLinkSession(parsed);
  }

  get consumed(): boolean {
    return this.#consumed;
  }

  consume<T>(consumer: (secret: Uint8Array) => T): T {
    if (this.#consumed || this.#secretBytes === undefined) {
      throw new ClaimLinkError("claim_secret_already_consumed");
    }
    this.#consumed = true;
    const secret = this.#secretBytes;
    this.#secretBytes = undefined;
    try {
      return consumer(secret);
    } finally {
      secret.fill(0);
    }
  }
}

export function safeClaimUrl(locator: string, origin = DEFAULT_CLAIM_ORIGIN): string {
  validateLocator(locator);
  const expected = new URL(origin);
  if (expected.protocol !== "https:" || expected.origin !== origin) {
    throw new ClaimLinkError("invalid_expected_origin");
  }
  return `${origin}/claim/${locator}`;
}
