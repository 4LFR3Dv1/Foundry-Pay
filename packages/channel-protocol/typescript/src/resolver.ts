import {
  ClaimLinkError,
  DEFAULT_CLAIM_ORIGIN,
  safeClaimUrl,
  validateLocator,
} from "./claim-link.js";

export interface ResolverRequest {
  readonly method: "GET";
  readonly url: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly referrerPolicy: "no-referrer";
}

export interface ResolverResponse {
  readonly ok: boolean;
  json(): Promise<unknown>;
}

export type ResolverTransport = (request: ResolverRequest) => Promise<ResolverResponse>;

export function buildResolverRequest(
  locator: string,
  origin = DEFAULT_CLAIM_ORIGIN,
): ResolverRequest {
  validateLocator(locator);
  return Object.freeze({
    method: "GET",
    url: safeClaimUrl(locator, origin),
    headers: Object.freeze({
      accept: "application/json",
      "cache-control": "no-store",
    }),
    referrerPolicy: "no-referrer",
  });
}

export async function resolveClaim(
  locator: string,
  transport: ResolverTransport,
  origin = DEFAULT_CLAIM_ORIGIN,
): Promise<unknown> {
  try {
    const response = await transport(buildResolverRequest(locator, origin));
    if (!response.ok) {
      throw new ClaimLinkError("claim_unavailable");
    }
    return await response.json();
  } catch {
    // Deliberately collapse transport, missing, expired, consumed, and blocked
    // outcomes. The public resolver must not expose an enumeration oracle.
    throw new ClaimLinkError("claim_unavailable");
  }
}
