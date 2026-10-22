// Documentation example, not frontend source or production authentication.
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

export class ApiError extends Error {
  constructor(status, code, message, details = [], retryAfter = null) {
    super(message);
    Object.assign(this, { status, code, details, retryAfter });
  }
}

function apiBase(value, development = false) {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password ||
      url.search || url.hash || !["", "/"].includes(url.pathname)) {
    throw new Error("Use a backend HTTP(S) origin without credentials or /api suffix");
  }
  if (development && (!LOOPBACK.has(url.hostname) ||
      (globalThis.location && !LOOPBACK.has(globalThis.location.hostname)))) {
    throw new Error("Development access is only for a local browser and loopback backend");
  }
  if (url.protocol === "http:" && !LOOPBACK.has(url.hostname)) {
    throw new Error("Non-local buyer backends require HTTPS");
  }
  return url.origin;
}

async function jsonRequest(base, path, headers, { method = "GET", body, signal } = {}) {
  if (!(path === "/health" || path.startsWith("/api/")) || path.includes("\\")) {
    throw new Error("Use an API path on this backend; absolute URLs are forbidden");
  }
  const response = await fetch(base + path, {
    method, signal, cache: "no-store", credentials: "omit", redirect: "error",
    referrerPolicy: "no-referrer",
    headers: { ...headers, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let data;
  if (response.headers.get("Content-Type")?.includes("application/json")) {
    try { data = await response.json(); }
    catch { throw new ApiError(response.status, "INVALID_RESPONSE", "Backend returned invalid JSON"); }
  }
  if (!response.ok) {
    throw new ApiError(response.status, data?.error?.code ?? "HTTP_ERROR",
      data?.error?.message ?? `Backend returned HTTP ${response.status}`,
      data?.error?.details ?? [], response.headers.get("Retry-After"));
  }
  if (data === undefined) throw new ApiError(response.status, "INVALID_RESPONSE", "Backend did not return JSON");
  return data;
}

export function createDevelopmentApi({ baseUrl, token }) {
  const base = apiBase(baseUrl, true);
  if (typeof token !== "string" || token.length < 32) throw new Error("Enter a private local development token at runtime");
  return (path, options) => jsonRequest(base, path,
    path === "/health" || path.split("?")[0] === "/api/orders/parse" ? {} : { "X-Dev-Access-Token": token }, options);
}

export function createBuyerApi({ baseUrl, linkToken }) {
  const base = apiBase(baseUrl);
  if (!/^[A-Za-z0-9_-]{43}$/.test(linkToken)) throw new Error("Use the complete confirmation-link token");
  const path = `/api/confirm/${encodeURIComponent(linkToken)}`;
  let authorization;
  const call = (suffix, options) => jsonRequest(base, path + suffix,
    authorization ? { Authorization: `Bearer ${authorization}` } : {}, options);
  return {
    card: (signal) => call("", { signal }),
    requestOtp: () => {
      authorization = undefined;
      return call("/otp", { method: "POST", body: {} });
    },
    async verify(code) {
      if (!/^[0-9]{6}$/.test(String(code))) throw new Error("Enter the six-digit code sent to your phone.");
      authorization = undefined;
      const result = await call("/verify", { method: "POST", body: { code: String(code) } });
      authorization = result.access_token; // Closure memory only; never URL/storage/logging.
      return { token_type: result.token_type, expires_at: result.expires_at };
    },
    details: (signal) => call("/details", { signal }),
    location: (body) => call("/location", { method: "PATCH", body }),
    respond: (body) => call("/response", { method: "PATCH", body }),
    request: (body) => call("/request", { method: "PATCH", body }),
    clear: () => { authorization = undefined; },
  };
}
