const FALLBACK_EXPIRES_MS = 7 * 24 * 60 * 60 * 1000;

function decodeBase64Url(input: string): string | null {
  try {
    const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
    const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
    return atob(normalized + padding);
  } catch {
    return null;
  }
}

export function getTokenExpiryMs(token: string): number | null {
  const parts = token.split(".");
  if (parts.length < 2) {
    return null;
  }
  const payloadRaw = decodeBase64Url(parts[1]);
  if (!payloadRaw) {
    return null;
  }
  try {
    const payload = JSON.parse(payloadRaw) as Record<string, unknown>;
    const exp = payload.exp;
    if (typeof exp === "number" && Number.isFinite(exp)) {
      return exp * 1000;
    }
    if (typeof exp === "string") {
      const parsed = Number(exp);
      if (Number.isFinite(parsed)) {
        return parsed * 1000;
      }
    }
    return null;
  } catch {
    return null;
  }
}

export function computeExpiresAt(token: string): number {
  const fromToken = getTokenExpiryMs(token);
  if (fromToken && Number.isFinite(fromToken)) {
    return fromToken;
  }
  return Date.now() + FALLBACK_EXPIRES_MS;
}
