import { describe, expect, it } from "vitest";
import { handleParse as handler } from "../api/parse.ts";

const post = (body: unknown, headers: Record<string, string> = {}) =>
  new Request("https://lannpya.app/api/parse", {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });

describe("POST /api/parse (serverless route, NFR-08)", () => {
  it("parses a batch and reports offline demo mode when no AI key is set", async () => {
    const res = await handler(post({ text: "09777123456\nကမာရွတ် Junction Square\n\nဗဟန်း" }), {});
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.mode).toBe("offline-demo");
    expect(body.summary).toMatchObject({ total: 2, green: 1, red: 1 });
    expect(body.orders[0].triage.level).toBe("green");
  });

  it("streams one JSON line per order when asked (NFR-01)", async () => {
    const res = await handler(post({ text: "09777123456\nကမာရွတ်\n\nဗဟန်း" }, { accept: "application/x-ndjson" }), {});
    expect(res.headers.get("content-type")).toContain("application/x-ndjson");
    const lines = (await res.text()).trim().split("\n").map((l) => JSON.parse(l));
    expect(lines.map((l) => l.type)).toEqual(["order", "order", "summary"]);
    expect(lines[2]).toMatchObject({ mode: "offline-demo", summary: { total: 2 } });
  });

  it("rejects other methods, bad JSON and empty or oversized text", async () => {
    expect((await handler(new Request("https://x/api/parse"), {})).status).toBe(405);
    expect((await handler(post("{nope"), {})).status).toBe(400);
    expect((await handler(post({ text: "  " }), {})).status).toBe(400);
    expect((await handler(post({ text: "x".repeat(100_001) }), {})).status).toBe(413);
  });
});
