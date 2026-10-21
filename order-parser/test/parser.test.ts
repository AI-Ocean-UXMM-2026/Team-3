import { describe, expect, it, vi } from "vitest";
import rabbit from "rabbit-node";
import { splitOrders } from "../src/split.ts";
import { parseOrder, parseBatch, parseBatchStream } from "../src/parser.ts";
import { correctField, CorrectionError } from "../src/correct.ts";
import { DictionaryGeocoder } from "../src/places.ts";
import { HeuristicExtractor } from "../src/ai/offline.ts";
import type { AddressExtractor } from "../src/ai/types.ts";

const geocoder = new DictionaryGeocoder();

function fakeAi(output: Record<string, unknown>): AddressExtractor & { seen: string[] } {
  const seen: string[] = [];
  return {
    seen,
    extract: async (text) => {
      seen.push(text);
      return { raw: output, model: "fake", offline: false };
    },
  };
}

describe("splitting a pasted batch (HLR-01)", () => {
  it("splits on blank lines", () => {
    expect(splitOrders("a\n09\n\n\nb\n\n  \nc")).toEqual(["a\n09", "b", "c"]);
  });

  it("splits on numbered orders written back to back", () => {
    expect(splitOrders("1. Ma Hla\nBahan\n2. Ko Ko\nTamwe\n၃။ Daw Mya\nYankin")).toEqual([
      "1. Ma Hla\nBahan",
      "2. Ko Ko\nTamwe",
      "၃။ Daw Mya\nYankin",
    ]);
  });

  it("splits on --- separators", () => {
    expect(splitOrders("a\n---\nb")).toEqual(["a", "b"]);
    expect(splitOrders("a\n\n---\n\nb")).toEqual(["a", "b"]);
  });
});

describe("parsing one order", () => {
  const amberOrder = `Ma Thida
09-777-123-456
တာမွေ အဆွေတော်နား ၄ ထပ်တိုက် ညာဘက်ခန်း
ညနေ ၃ နာရီမှ လာပါ
COD 28000`;
  const aiAnswer = {
    landmark: "အဆွေတော်နား",
    street: null,
    floor_unit: "၄ ထပ်တိုက် ညာဘက်ခန်း",
    instructions: "ညနေ ၃ နာရီမှ လာပါ",
    vague_phrases: ["အဆွေတော်နား"],
  };

  it("fills the FR-1.2 fields from rules, dictionary and AI, and marks only AI fields with a sparkle", async () => {
    const order = await parseOrder(amberOrder, { extractor: fakeAi(aiAnswer), geocoder });
    expect(order.fields).toMatchObject({
      customerName: "Ma Thida",
      phone: "09777123456",
      township: { id: "tamwe" },
      landmark: "အဆွေတော်နား",
      floorUnit: "၄ ထပ်တိုက် ညာဘက်ခန်း",
      codAmount: 28000,
      prepaid: false,
      instructions: "ညနေ ၃ နာရီမှ လာပါ",
    });
    expect(order.sources).toMatchObject({ phone: "rule", codAmount: "rule", township: "dictionary", landmark: "ai" });
    expect(order.aiFilled.sort()).toEqual(["floorUnit", "instructions", "landmark"]);
  });

  it("sends the AI only the redacted address text", async () => {
    const ai = fakeAi(aiAnswer);
    await parseOrder(amberOrder, { extractor: ai, geocoder });
    expect(ai.seen[0]).not.toMatch(/Thida|777|28000/);
  });

  it("is Amber and highlights the vague words in the original text (HLR-12)", async () => {
    const order = await parseOrder(amberOrder, { extractor: fakeAi(aiAnswer), geocoder });
    expect(order.triage.level).toBe("amber");
    expect(order.highlights.map((h) => order.text.slice(h.start, h.end))).toEqual(["အဆွေတော်နား"]);
  });

  it("is Green when the address names a place on the map", async () => {
    const order = await parseOrder("Ko Aung\n09777123456\nကမာရွတ် Junction Square နောက်ဘက်\nCOD 15000", {
      extractor: fakeAi({ landmark: "Junction Square" }),
      geocoder,
    });
    expect(order.triage.level).toBe("green");
    expect(order.location).toMatchObject({ name: "Junction Square", source: "dictionary" });
  });

  it("finds the township, road and Green status even when the AI is down (rules first)", async () => {
    const down: AddressExtractor = { extract: () => Promise.reject(new Error("offline")) };
    const order = await parseOrder("09777123456 Sanchaung, No. 45, Baho Road", { extractor: down, geocoder });
    expect(order.triage.level).toBe("green");
    expect(order.fields.street).toBe("Baho Road");
    expect(order.ai).toMatchObject({ ok: false });
  });

  it("is Red when the phone is missing", async () => {
    const order = await parseOrder("ဗဟန်း Shwedagon Pagoda", { extractor: fakeAi({}), geocoder });
    expect(order.triage.level).toBe("red");
  });

  it("converts Zawgyi input before parsing (HLR-02)", async () => {
    const zawgyi = rabbit.uni2zg("မြို့နယ် တာမွေ အဆွေတော်နား");
    const order = await parseOrder(`09777123456\n${zawgyi}`, { extractor: new HeuristicExtractor(), geocoder });
    expect(order.wasZawgyi).toBe(true);
    expect(order.fields.township?.id).toBe("tamwe");
  });

  it("drops AI values that are not in the text and records why", async () => {
    const order = await parseOrder("09777123456\nတာမွေ အဆွေတော်နား", {
      extractor: fakeAi({ landmark: "Ocean Tamwe" }),
      geocoder,
    });
    expect(order.fields.landmark).toBeNull();
    expect(order.ai.dropped).toEqual([{ field: "landmark", value: "Ocean Tamwe", reason: "not_in_text" }]);
    expect(order.triage.level).toBe("amber");
  });

  it("reports offline demo mode when a fallback answered", async () => {
    const order = await parseOrder("09777123456\nတာမွေ အဆွေတော်နား", {
      extractor: new HeuristicExtractor(),
      geocoder,
    });
    expect(order.ai).toMatchObject({ ok: true, offline: true, model: "heuristic" });
  });
});

describe("parsing a batch (HLR-01, NFR-01)", () => {
  const batch = "09777123456\nကမာရွတ် Junction Square\n\n09450123456\nတာမွေ အဆွေတော်နား\n\nဗဟန်း";

  it("parses every order and keeps their order", async () => {
    const result = await parseBatch(batch, { extractor: fakeAi({}), geocoder });
    expect(result.orders.map((o) => o.triage.level)).toEqual(["green", "amber", "red"]);
    expect(result.orders.map((o) => o.id)).toEqual(["order-1", "order-2", "order-3"]);
    expect(result.summary).toEqual({ total: 3, green: 1, amber: 1, red: 0 + 1, offline: false });
  });

  it("streams results one order at a time", async () => {
    const seen: string[] = [];
    for await (const order of parseBatchStream(batch, { extractor: fakeAi({}), geocoder })) seen.push(order.id);
    expect(seen).toEqual(["order-1", "order-2", "order-3"]);
  });

  it("limits how many AI calls run at once", async () => {
    let running = 0;
    let peak = 0;
    const slow: AddressExtractor = {
      extract: async () => {
        peak = Math.max(peak, ++running);
        await new Promise((r) => setTimeout(r, 5));
        running--;
        return { raw: {}, model: "slow", offline: false };
      },
    };
    const many = Array.from({ length: 10 }, (_, i) => `09777123${String(i).padStart(3, "0")}\nBahan`).join("\n\n");
    await parseBatch(many, { extractor: slow, geocoder, concurrency: 3 });
    expect(peak).toBe(3);
  });

  it("flags the whole batch as offline demo mode if any order used a fallback", async () => {
    const result = await parseBatch(batch, { extractor: new HeuristicExtractor(), geocoder });
    expect(result.summary.offline).toBe(true);
  });
});

describe("one-tap correction and re-triage (HLR-13)", () => {
  const deps = { extractor: fakeAi({ landmark: "အဆွေတော်နား" }), geocoder };

  it("re-triages after the dispatcher fixes a field, and removes the sparkle", async () => {
    const amber = await parseOrder("09777123456\nကမာရွတ် အဆွေတော်နား", deps);
    expect(amber.triage.level).toBe("amber");
    const fixed = await correctField(amber, "landmark", "Junction Square", { geocoder });
    expect(fixed.triage.level).toBe("green");
    expect(fixed.sources.landmark).toBe("dispatcher");
    expect(fixed.aiFilled).not.toContain("landmark");
    expect(amber.triage.level).toBe("amber");
  });

  it("validates a corrected phone with the same rules", async () => {
    const red = await parseOrder("ကမာရွတ် Junction Square", deps);
    expect(red.triage.level).toBe("red");
    const fixed = await correctField(red, "phone", "၀၉ ၇၇၇ ၁၂၃ ၄၅၆", { geocoder });
    expect(fixed.fields.phone).toBe("09777123456");
    expect(fixed.triage.level).toBe("green");
  });

  it("accepts a township by name or id and rejects unknown ones", async () => {
    const order = await parseOrder("09777123456\nJunction Square", deps);
    expect((await correctField(order, "township", "ကမာရွတ်", { geocoder })).fields.township?.id).toBe("kamayut");
    expect((await correctField(order, "township", "kamayut", { geocoder })).triage.level).toBe("green");
    await expect(correctField(order, "township", "Atlantis", { geocoder })).rejects.toThrow(CorrectionError);
  });

  it("reads a corrected COD amount with the money rules", async () => {
    const order = await parseOrder("09777123456\nကမာရွတ် Junction Square", deps);
    expect((await correctField(order, "codAmount", "၂ သောင်း", { geocoder })).fields.codAmount).toBe(20000);
  });

  it("accepts a pin from the dispatcher or buyer as a mapped location", async () => {
    const amber = await parseOrder("09777123456\nကမာရွတ် အဆွေတော်နား", deps);
    const pinned = await correctField(amber, "pin", { lat: 16.81, lng: 96.13 }, { geocoder });
    expect(pinned.location).toMatchObject({ source: "dispatcher", lat: 16.81 });
    expect(pinned.triage.level).toBe("green");
  });

  it("does not call the AI again", async () => {
    const ai = fakeAi({});
    const order = await parseOrder("09777123456\nကမာရွတ်", { extractor: ai, geocoder });
    await correctField(order, "landmark", "Hledan Centre", { geocoder });
    expect(ai.seen).toHaveLength(1);
  });
});
