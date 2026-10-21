import { describe, expect, it, vi } from "vitest";
import { redactForAi } from "../src/redact.ts";
import { validateAiOutput, AiOutputError } from "../src/ai/schema.ts";
import { GeminiExtractor, AiUnavailableError } from "../src/ai/gemini.ts";
import { RecordedExtractor, HeuristicExtractor } from "../src/ai/offline.ts";
import { ChainExtractor } from "../src/ai/chain.ts";
import type { AddressExtractor } from "../src/ai/types.ts";

const order = `Name: Ma Thida
09-777-123-456
COD 28,000 ks
ပစ္စည်း: Floral Summer Dress
တာမွေ အဆွေတော်နား ၄ ထပ်တိုက် ညာဘက်ခန်း
ညနေ ၃ နာရီမှ လာပါ`;

describe("privacy: only address text reaches the AI (HLR-06)", () => {
  const sent = redactForAi(order);

  it("removes the name, phone, amount and item", () => {
    expect(sent).not.toMatch(/Thida|777|123|456|28,000|COD|Dress/);
  });

  it("keeps the address and delivery notes", () => {
    expect(sent).toContain("အဆွေတော်နား ၄ ထပ်တိုက် ညာဘက်ခန်း");
    expect(sent).toContain("ညနေ ၃ နာရီမှ လာပါ");
  });

  it("removes the name when the order starts with its number", () => {
    expect(redactForAi("1. Ma Thida\n09777123456\nကမာရွတ်")).toBe("ကမာရွတ်");
  });

  it("drops a phone label left on its own", () => {
    expect(redactForAi("ဖုန်း ၀၉၇၉၁၂၃၄၅၆၇\nဗဟန်း")).toBe("ဗဟန်း");
    expect(redactForAi("Ph: 09777123456\nဗဟန်း")).toBe("ဗဟန်း");
  });

  it("removes a phone written inside the address line", () => {
    expect(redactForAi("ဗဟန်း 09777123456 ကိုဆက်ပါ")).toBe("ဗဟန်း ကိုဆက်ပါ");
  });
});

describe("AI output validation: fixed schema, nothing made up (HLR-05)", () => {
  const source = "တာမွေ အဆွေတော်နား ၄ ထပ်တိုက် ညာဘက်ခန်း\nညနေ ၃ နာရီမှ လာပါ";
  const good = {
    landmark: "အဆွေတော်နား",
    street: null,
    floor_unit: "၄ ထပ်တိုက် ညာဘက်ခန်း",
    instructions: "ညနေ ၃ နာရီမှ လာပါ",
    vague_phrases: ["အဆွေတော်နား"],
  };

  it("accepts output that follows the schema and quotes the text", () => {
    const { fields, dropped } = validateAiOutput(good, source);
    expect(fields).toEqual({
      landmark: "အဆွေတော်နား",
      street: null,
      floorUnit: "၄ ထပ်တိုက် ညာဘက်ခန်း",
      instructions: "ညနေ ၃ နာရီမှ လာပါ",
      vaguePhrases: ["အဆွေတော်နား"],
    });
    expect(dropped).toEqual([]);
  });

  it("rejects output that breaks the schema", () => {
    expect(() => validateAiOutput({ landmark: 4 }, source)).toThrow(AiOutputError);
    expect(() => validateAiOutput("not json", source)).toThrow(AiOutputError);
  });

  it("drops a value that is not in the original text (no hallucinated landmarks)", () => {
    const { fields, dropped } = validateAiOutput({ ...good, landmark: "Junction Square" }, source);
    expect(fields.landmark).toBeNull();
    expect(dropped).toEqual([{ field: "landmark", value: "Junction Square", reason: "not_in_text" }]);
  });

  it("never lets the AI supply a phone number", () => {
    const { fields, dropped } = validateAiOutput({ ...good, instructions: "09777123456" }, `${source} 09777123456`);
    expect(fields.instructions).toBeNull();
    expect(dropped[0]).toMatchObject({ field: "instructions", reason: "looks_like_phone_or_money" });
  });

  it("ignores spacing and punctuation differences when checking the quote", () => {
    const { fields } = validateAiOutput({ ...good, floor_unit: "၄ထပ်တိုက်၊ ညာဘက်ခန်း" }, source);
    expect(fields.floorUnit).toBe("၄ထပ်တိုက်၊ ညာဘက်ခန်း");
  });
});

function fakeGeminiFetch(body: unknown, status = 200) {
  return vi.fn(async (_url: string | URL | Request, _init?: RequestInit) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
}

describe("Gemini Flash extractor (behind the swappable interface, NFR-07)", () => {
  const reply = { landmark: "x", street: null, floor_unit: null, instructions: null, vague_phrases: [] };

  it("asks for JSON that matches our schema and returns the parsed object", async () => {
    const fetch = fakeGeminiFetch({ candidates: [{ content: { parts: [{ text: JSON.stringify(reply) }] } }] });
    const ai = new GeminiExtractor({ apiKey: "test-key", model: "gemini-test-flash", fetch });
    const result = await ai.extract("တာမွေ x");

    expect(result).toEqual({ raw: reply, model: "gemini-test-flash", offline: false });
    const [url, init] = fetch.mock.calls[0];
    expect(String(url)).toContain("/models/gemini-test-flash:generateContent");
    expect((init!.headers as Record<string, string>)["x-goog-api-key"]).toBe("test-key");
    const body = JSON.parse(String(init!.body));
    expect(body.generationConfig).toMatchObject({ responseMimeType: "application/json", temperature: 0 });
    expect(Object.keys(body.generationConfig.responseSchema.properties)).toEqual([
      "landmark",
      "street",
      "floor_unit",
      "instructions",
      "vague_phrases",
    ]);
    expect(body.contents[0].parts[0].text).toContain("တာမွေ x");
  });

  it("reads the key and model from the environment", () => {
    const ai = GeminiExtractor.fromEnv({ GEMINI_API_KEY: "k", GEMINI_MODEL: "m" });
    expect(ai?.model).toBe("m");
    expect(GeminiExtractor.fromEnv({})).toBeNull();
  });

  it("raises AiUnavailableError on an HTTP error", async () => {
    const ai = new GeminiExtractor({ apiKey: "k", fetch: fakeGeminiFetch({ error: "quota" }, 429) });
    await expect(ai.extract("x")).rejects.toThrow(AiUnavailableError);
  });

  it("raises AiUnavailableError when the reply has no JSON", async () => {
    const ai = new GeminiExtractor({ apiKey: "k", fetch: fakeGeminiFetch({ candidates: [] }) });
    await expect(ai.extract("x")).rejects.toThrow(AiUnavailableError);
  });

  it("gives up after the timeout", async () => {
    const hang = vi.fn(
      (_url: string | URL | Request, init?: RequestInit) =>
        new Promise<Response>((_, reject) => init!.signal!.addEventListener("abort", () => reject(init!.signal!.reason))),
    );
    const ai = new GeminiExtractor({ apiKey: "k", fetch: hang, timeoutMs: 20 });
    await expect(ai.extract("x")).rejects.toThrow(AiUnavailableError);
  });
});

describe("offline demo fallback (HLR-36)", () => {
  it("replays a recorded answer for known text", async () => {
    const rec = new RecordedExtractor([{ input: "တာမွေ  အဆွေတော်နား", output: { landmark: "အဆွေတော်နား" } }]);
    expect(await rec.extract("တာမွေ အဆွေတော်နား")).toEqual({
      raw: { landmark: "အဆွေတော်နား" },
      model: "recorded",
      offline: true,
    });
    await expect(rec.extract("something else")).rejects.toThrow();
  });

  it("has a no-AI heuristic for anything not recorded", async () => {
    const { raw } = await new HeuristicExtractor().extract("တာမွေ အဆွေတော်နား ၄ ထပ်တိုက်\nညနေ ၃ နာရီမှ လာပါ");
    const { fields } = validateAiOutput(raw, "တာမွေ အဆွေတော်နား ၄ ထပ်တိုက်\nညနေ ၃ နာရီမှ လာပါ");
    expect(fields).toMatchObject({
      landmark: "အဆွေတော်",
      floorUnit: "၄ ထပ်တိုက်",
      instructions: "ညနေ ၃ နာရီမှ လာပါ",
      vaguePhrases: ["အဆွေတော်နား"],
    });
  });

  it("uses the live model first and falls back, marking the result offline", async () => {
    const live: AddressExtractor = { extract: async () => ({ raw: { landmark: "a" }, model: "live", offline: false }) };
    const down: AddressExtractor = {
      extract: async () => {
        throw new AiUnavailableError("down");
      },
    };
    const backup: AddressExtractor = { extract: async () => ({ raw: { landmark: "b" }, model: "recorded", offline: true }) };

    expect(await new ChainExtractor([live, backup]).extract("x")).toMatchObject({ model: "live", offline: false });
    expect(await new ChainExtractor([down, backup]).extract("x")).toMatchObject({ model: "recorded", offline: true });
  });

  it("marks the result offline even when a later live extractor answers", async () => {
    const down: AddressExtractor = { extract: async () => Promise.reject(new Error("net")) };
    const other: AddressExtractor = { extract: async () => ({ raw: {}, model: "other", offline: false }) };
    expect(await new ChainExtractor([down, other]).extract("x")).toMatchObject({ offline: true });
  });

  it("fails only when every extractor fails", async () => {
    const down: AddressExtractor = { extract: async () => Promise.reject(new Error("net")) };
    await expect(new ChainExtractor([down, down]).extract("x")).rejects.toThrow(AiUnavailableError);
  });
});
