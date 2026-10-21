import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { createExtractor, SAMPLE_RECORDINGS } from "../src/pipeline.ts";
import { parseBatch } from "../src/parser.ts";
import { DictionaryGeocoder } from "../src/places.ts";
import { validateAiOutput } from "../src/ai/schema.ts";

const samples = readFileSync(new URL("../data/sample-orders.txt", import.meta.url), "utf8");

describe("demo sample set (HLR-35) in offline demo mode (HLR-36)", async () => {
  const result = await parseBatch(samples, { extractor: createExtractor({}), geocoder: new DictionaryGeocoder() });

  it("has 20 orders, all answered from recordings", () => {
    expect(result.orders).toHaveLength(20);
    expect(result.orders.every((o) => o.ai.model === "recorded")).toBe(true);
    expect(result.summary.offline).toBe(true);
  });

  it("every recorded answer follows the schema and quotes its text", () => {
    for (const r of SAMPLE_RECORDINGS) expect(validateAiOutput(r.output, r.input).dropped).toEqual([]);
  });

  it("triages each order as expected", () => {
    expect(result.orders.map((o) => o.triage.level[0].toUpperCase()).join("")).toBe("GAGGGRAGRGAGGRGGGAGG");
  });

  it("auto-classifies over 60% Green (PRD success metric)", () => {
    expect(result.summary.green / result.summary.total).toBeGreaterThan(0.6);
  });

  it("converted the Zawgyi order", () => {
    const o = result.orders[17];
    expect(o.wasZawgyi).toBe(true);
    expect(o.fields.township?.id).toBe("hlaing-tharyar");
  });

  it("explains every Red order", () => {
    const red = result.orders.filter((o) => o.triage.level === "red");
    expect(red.map((o) => o.triage.reasons.map((r) => r.code))).toEqual([["no_phone"], ["invalid_phone"], ["unknown_township"]]);
  });

  it("never sends a sample's phone number or name to the AI", () => {
    for (const o of result.orders) {
      if (o.fields.phone) expect(o.addressText).not.toContain(o.fields.phone.slice(-4));
      if (o.fields.customerName) expect(o.addressText).not.toContain(o.fields.customerName);
    }
  });
});

describe("choosing the AI", () => {
  it("uses Gemini first when a key is set, then the offline fallbacks", async () => {
    const calls: string[] = [];
    const fetch = async (url: string | URL | Request) => {
      calls.push(String(url));
      return new Response("{}", { status: 503 });
    };
    const extractor = createExtractor({ GEMINI_API_KEY: "k" }, { fetch });
    const result = await extractor.extract(SAMPLE_RECORDINGS[0].input);
    expect(calls).toHaveLength(1);
    expect(result).toMatchObject({ model: "recorded", offline: true });
  });

  it("falls back to the heuristic for text with no recording", async () => {
    expect(await createExtractor({}).extract("တာမွေ ဈေးနား")).toMatchObject({ model: "heuristic", offline: true });
  });
});
