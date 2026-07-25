const CLAIM_FRAGMENT = /(https:\/\/[^\s"'<>]*\/claim\/[A-Za-z0-9_-]+)#(?:[^\s"'<>]+)/giu;
const ENCODED_FRAGMENT = /(%23|%2523)[A-Za-z0-9_%.-]+/giu;
export const REDACTED = "[REDACTED_CLAIM_SECRET]";

function variants(secret: string): string[] {
  const encoded = encodeURIComponent(secret);
  return [secret, encoded, encodeURIComponent(encoded)].filter((value) => value.length > 0);
}

export function redactString(value: string, secrets: readonly string[] = []): string {
  let output = value.replace(CLAIM_FRAGMENT, `$1#${REDACTED}`);
  output = output.replace(ENCODED_FRAGMENT, `$1${REDACTED}`);
  for (const secret of secrets.flatMap(variants).sort((a, b) => b.length - a.length)) {
    output = output.replaceAll(secret, REDACTED);
  }
  return output;
}

export function redactUnknown<T>(value: T, secrets: readonly string[] = []): T {
  const seen = new WeakMap<object, unknown>();

  function visit(input: unknown): unknown {
    if (typeof input === "string") {
      return redactString(input, secrets);
    }
    if (
      input === null ||
      typeof input === "number" ||
      typeof input === "boolean" ||
      typeof input === "undefined" ||
      typeof input === "bigint"
    ) {
      return input;
    }
    if (input instanceof Error) {
      if (seen.has(input)) {
        return "[Circular]";
      }
      const result: Record<string, unknown> = {
        name: redactString(input.name, secrets),
        message: redactString(input.message, secrets),
      };
      seen.set(input, result);
      if (input.stack !== undefined) {
        result.stack = redactString(input.stack, secrets);
      }
      if ("cause" in input && input.cause !== undefined) {
        result.cause = visit(input.cause);
      }
      return Object.freeze(result);
    }
    if (Array.isArray(input)) {
      if (seen.has(input)) {
        return "[Circular]";
      }
      const result: unknown[] = [];
      seen.set(input, result);
      for (const item of input) {
        result.push(visit(item));
      }
      return result;
    }
    if (typeof input === "object") {
      if (seen.has(input)) {
        return "[Circular]";
      }
      const result: Record<string, unknown> = {};
      seen.set(input, result);
      for (const [key, item] of Object.entries(input)) {
        result[redactString(key, secrets)] = visit(item);
      }
      return result;
    }
    return redactString(String(input), secrets);
  }

  return visit(value) as T;
}

export function safeTelemetryPayload<T>(value: T, secrets: readonly string[] = []): T {
  return redactUnknown(value, secrets);
}

export function safeEvidencePayload<T>(value: T, secrets: readonly string[] = []): T {
  return redactUnknown(value, secrets);
}
