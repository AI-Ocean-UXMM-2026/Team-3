import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, createBuyerApi, createDevelopmentApi } from "./lannpya-client.mjs";

const baseUrl = "http://127.0.0.1:8000";
const token = "local-test-secret-" + "x".repeat(32);

test("development token stays on the chosen loopback backend", async () => {
  assert.throws(() => createDevelopmentApi({ baseUrl: "https://public.example.invalid", token }));
  const calls = [];
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ status: "ok" }); };
  const api = createDevelopmentApi({ baseUrl, token });
  await api("/health");
  await api("/api/orders");
  assert.equal(calls[0].options.headers["X-Dev-Access-Token"], undefined);
  assert.equal(calls[1].options.headers["X-Dev-Access-Token"], token);
  assert.equal(calls[1].options.credentials, "omit");
  await assert.rejects(api("https://other.example.invalid/api/orders"));
});

test("buyer requests a six-digit OTP and keeps the verified credential separate", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return Response.json(url.endsWith("/verify") ? { access_token: "buyer-secret", token_type: "Bearer", expires_at: "2099-01-01T00:00:00Z" } : {});
  };
  const buyer = createBuyerApi({ baseUrl, linkToken: "a".repeat(43) });
  await buyer.requestOtp();
  await assert.rejects(buyer.verify("0000"), /six-digit/);
  const verification = await buyer.verify("123456");
  assert.equal(verification.access_token, undefined);
  await buyer.details();
  assert.deepEqual(JSON.parse(calls[0].options.body), {});
  assert.deepEqual(JSON.parse(calls[1].options.body), { code: "123456" });
  assert.equal(calls[2].options.headers.Authorization, "Bearer buyer-secret");
  assert.equal(calls[2].options.headers["X-Dev-Access-Token"], undefined);
  buyer.clear();
  await buyer.card();
  assert.equal(calls[3].options.headers.Authorization, undefined);
});

test("errors preserve field locations and browser-visible Retry-After", async () => {
  globalThis.fetch = async () => Response.json({ error: { code: "BUYER_RATE_LIMITED", message: "Wait", details: [] } },
    { status: 429, headers: { "Retry-After": "60" } });
  const api = createDevelopmentApi({ baseUrl, token });
  await assert.rejects(api("/api/orders"), error => error instanceof ApiError && error.status === 429 && error.retryAfter === "60");
});

test("plain proxy errors and malformed JSON do not become misleading successes", async () => {
  const api = createDevelopmentApi({ baseUrl, token });
  globalThis.fetch = async () => new Response("private proxy details", { status: 503 });
  await assert.rejects(api("/api/orders"), error => error.status === 503 && !error.message.includes("private"));
  globalThis.fetch = async () => new Response("{bad", { headers: { "Content-Type": "application/json" } });
  await assert.rejects(api("/api/orders"), error => error.code === "INVALID_RESPONSE");
});
